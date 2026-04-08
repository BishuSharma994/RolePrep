from __future__ import annotations

import ctypes
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

try:
    from faster_whisper import WhisperModel
except ModuleNotFoundError:  # pragma: no cover - exercised only when dependency is missing
    WhisperModel = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "tiny"
_BASE_MODEL = "base"
_TINY_MODEL = "tiny"
_SMALL_MODEL = "small"
_KNOWN_MODELS = {_TINY_MODEL, _BASE_MODEL, _SMALL_MODEL}
_LOW_MEMORY_FORCE_TINY_BYTES = int(1.5 * 1024 * 1024 * 1024)
_BLOCK_SMALL_BELOW_BYTES = int(3 * 1024 * 1024 * 1024)


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


@dataclass(slots=True)
class STTSegment:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "text": self.text,
        }


class STTService:
    _model_cache: dict[tuple[str, str, int, int], Any] = {}
    _resolved_model_cache: dict[tuple[str, str, int, int], str] = {}
    _model_lock = Lock()

    def __init__(self, model_name: str | None = None, compute_type: str = "int8"):
        requested_model = self._normalize_model_name(model_name or os.getenv("WHISPER_MODEL") or _DEFAULT_MODEL)
        self.model_name = requested_model
        self.compute_type = "int8"
        self.cpu_threads = max(1, min(2, os.cpu_count() or 1))
        self.num_workers = 1

        if compute_type != "int8":
            logger.info("Ignoring requested Whisper compute_type=%s and forcing int8 for memory safety", compute_type)

        logger.info(
            "Whisper configuration prepared: requested_model=%s compute_type=%s cpu_threads=%s num_workers=%s",
            self.model_name,
            self.compute_type,
            self.cpu_threads,
            self.num_workers,
        )

    @staticmethod
    def _normalize_model_name(model_name: str) -> str:
        normalized = str(model_name or "").strip()
        if not normalized:
            return _DEFAULT_MODEL

        lowered = normalized.lower()
        return lowered if lowered in _KNOWN_MODELS else normalized

    @staticmethod
    def _available_memory_bytes() -> int | None:
        try:
            if os.name == "nt":
                memory_status = _MemoryStatusEx()
                memory_status.dwLength = ctypes.sizeof(_MemoryStatusEx)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status)):
                    return int(memory_status.ullAvailPhys)
        except Exception:
            logger.debug("Unable to read available system memory via Windows API", exc_info=True)

        try:
            if hasattr(os, "sysconf"):
                page_size = int(os.sysconf("SC_PAGE_SIZE"))
                available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
                if page_size > 0 and available_pages > 0:
                    return page_size * available_pages
        except (AttributeError, OSError, ValueError):
            logger.debug("Unable to read available system memory via sysconf", exc_info=True)

        meminfo_path = Path("/proc/meminfo")
        if meminfo_path.exists():
            try:
                for line in meminfo_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("MemAvailable:"):
                        parts = line.split()
                        if len(parts) >= 2:
                            return int(parts[1]) * 1024
            except Exception:
                logger.debug("Unable to read available system memory from /proc/meminfo", exc_info=True)

        return None

    @staticmethod
    def _format_memory_gb(memory_bytes: int | None) -> str:
        if memory_bytes is None:
            return "unknown"
        return f"{memory_bytes / (1024 * 1024 * 1024):.2f} GB"

    def _candidate_model_names(self) -> list[str]:
        available_memory = self._available_memory_bytes()
        selected_model = self.model_name

        logger.info("Whisper memory check: available=%s", self._format_memory_gb(available_memory))

        if available_memory is None and selected_model == _SMALL_MODEL:
            logger.warning(
                "Available memory could not be determined; skipping Whisper model 'small' to reduce OOM risk"
            )
            selected_model = _BASE_MODEL
        elif available_memory is not None:
            if available_memory < _LOW_MEMORY_FORCE_TINY_BYTES:
                if selected_model != _TINY_MODEL:
                    logger.warning(
                        "Available memory is %s; forcing Whisper model '%s'",
                        self._format_memory_gb(available_memory),
                        _TINY_MODEL,
                    )
                selected_model = _TINY_MODEL
            elif available_memory < _BLOCK_SMALL_BELOW_BYTES and selected_model == _SMALL_MODEL:
                logger.warning(
                    "Available memory is %s; blocking Whisper model 'small' and falling back to '%s'",
                    self._format_memory_gb(available_memory),
                    _BASE_MODEL,
                )
                selected_model = _BASE_MODEL

        candidates: list[str] = []
        for candidate in (selected_model, _BASE_MODEL, _TINY_MODEL):
            if candidate not in candidates:
                candidates.append(candidate)

        if selected_model == _TINY_MODEL:
            return [_TINY_MODEL]

        if selected_model == _BASE_MODEL:
            return [candidate for candidate in candidates if candidate in {_BASE_MODEL, _TINY_MODEL}]

        if selected_model == _SMALL_MODEL:
            return [candidate for candidate in candidates if candidate in {_SMALL_MODEL, _BASE_MODEL, _TINY_MODEL}]

        return candidates

    def _model_cache_key(self, model_name: str) -> tuple[str, str, int, int]:
        return (model_name, self.compute_type, self.cpu_threads, self.num_workers)

    def _request_cache_key(self) -> tuple[str, str, int, int]:
        return self._model_cache_key(self.model_name)

    def _get_model(self):
        if WhisperModel is None:
            raise RuntimeError("faster-whisper is not installed")

        request_cache_key = self._request_cache_key()
        resolved_model_name = self._resolved_model_cache.get(request_cache_key)
        if resolved_model_name is not None:
            model = self._model_cache.get(self._model_cache_key(resolved_model_name))
            if model is not None:
                return model

        model_candidates = self._candidate_model_names()
        model = None
        last_error: Exception | None = None

        for candidate in model_candidates:
            cache_key = self._model_cache_key(candidate)
            model = self._model_cache.get(cache_key)
            if model is not None:
                self._resolved_model_cache[request_cache_key] = candidate
                logger.info("Using cached Whisper model: selected_model=%s requested_model=%s", candidate, self.model_name)
                return model

        with self._model_lock:
            resolved_model_name = self._resolved_model_cache.get(request_cache_key)
            if resolved_model_name is not None:
                model = self._model_cache.get(self._model_cache_key(resolved_model_name))
                if model is not None:
                    return model

            for candidate in model_candidates:
                cache_key = self._model_cache_key(candidate)
                model = self._model_cache.get(cache_key)
                if model is not None:
                    self._resolved_model_cache[request_cache_key] = candidate
                    logger.info(
                        "Using cached Whisper model after lock: selected_model=%s requested_model=%s",
                        candidate,
                        self.model_name,
                    )
                    return model

                try:
                    logger.info(
                        "Loading Whisper model: selected_model=%s requested_model=%s compute_type=%s cpu_threads=%s num_workers=%s",
                        candidate,
                        self.model_name,
                        self.compute_type,
                        self.cpu_threads,
                        self.num_workers,
                    )
                    model = WhisperModel(
                        candidate,
                        compute_type=self.compute_type,
                        cpu_threads=self.cpu_threads,
                        num_workers=self.num_workers,
                    )
                    self._model_cache[cache_key] = model
                    self._resolved_model_cache[request_cache_key] = candidate
                    logger.info(
                        "Whisper model loaded successfully: selected_model=%s requested_model=%s",
                        candidate,
                        self.model_name,
                    )
                    return model
                except Exception as exc:  # pragma: no cover - depends on runtime/model availability
                    last_error = exc
                    if candidate != model_candidates[-1]:
                        logger.warning(
                            "Whisper model load failed for '%s'; attempting fallback",
                            candidate,
                            exc_info=True,
                        )
                    else:
                        logger.error(
                            "Whisper model load failed for '%s' and no more fallbacks remain",
                            candidate,
                            exc_info=True,
                        )

        attempted = ", ".join(model_candidates)
        raise RuntimeError(f"Unable to load Whisper model. Attempted: {attempted}") from last_error

    @staticmethod
    def _build_segments(raw_segments: list[Any]) -> list[STTSegment]:
        segments: list[STTSegment] = []
        for raw_segment in raw_segments:
            text = str(getattr(raw_segment, "text", "") or "").strip()
            segments.append(
                STTSegment(
                    start=float(getattr(raw_segment, "start", 0.0) or 0.0),
                    end=float(getattr(raw_segment, "end", 0.0) or 0.0),
                    text=text,
                )
            )
        return segments

    @staticmethod
    def _build_pause_metrics(segments: list[STTSegment], threshold: float = 0.5) -> dict[str, Any]:
        pauses: list[dict[str, float]] = []
        previous_end = None

        for index, segment in enumerate(segments):
            if previous_end is not None:
                gap = max(0.0, segment.start - previous_end)
                if gap > threshold:
                    pauses.append(
                        {
                            "after_segment_index": index - 1,
                            "before_segment_index": index,
                            "gap": round(gap, 3),
                        }
                    )
            previous_end = max(segment.end, previous_end or 0.0)

        avg_pause = round(sum(item["gap"] for item in pauses) / len(pauses), 3) if pauses else 0.0
        return {
            "pauses": pauses,
            "pause_count": len(pauses),
            "avg_pause": avg_pause,
        }

    def transcribe(self, file_path: str | Path) -> dict[str, Any]:
        audio_path = Path(file_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        model = self._get_model()
        raw_segments, _ = model.transcribe(
            str(audio_path),
            beam_size=1,
            best_of=1,
            condition_on_previous_text=False,
        )
        segments = self._build_segments(list(raw_segments))
        transcript = " ".join(segment.text for segment in segments if segment.text).strip()
        pause_metrics = self._build_pause_metrics(segments)

        return {
            "transcript": transcript,
            "segments": [segment.to_dict() for segment in segments],
            "pauses": pause_metrics["pauses"],
            "avg_pause": pause_metrics["avg_pause"],
            "pause_count": pause_metrics["pause_count"],
        }
