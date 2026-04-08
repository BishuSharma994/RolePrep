from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.services.answer_analysis_types import AnswerAnalysisRequest
from backend.services.answer_failure_engine import analyze_answer
from backend.services.stt_service import STTService

router = APIRouter()
TMP_AUDIO_DIR = Path("tmp_audio")


def _safe_suffix(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix else ".wav"


@router.post("/analyze-audio")
async def analyze_audio(
    file: UploadFile = File(...),
    role: str = Form(""),
    jd_text: str = Form(""),
    current_question: str = Form(""),
):
    TMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = TMP_AUDIO_DIR / f"{uuid.uuid4().hex}{_safe_suffix(file.filename)}"

    try:
        with temp_path.open("wb") as output_stream:
            shutil.copyfileobj(file.file, output_stream)

        stt_result = STTService().transcribe(temp_path)
        request = AnswerAnalysisRequest(
            role=str(role or ""),
            jd_text=str(jd_text or ""),
            current_question=str(current_question or ""),
            answer_text=str(stt_result.get("transcript") or ""),
        )
        analysis = analyze_answer(request)

        return {
            "transcript": stt_result.get("transcript", ""),
            "segments": stt_result.get("segments", []),
            "analysis": analysis.to_dict(),
            "audio_metrics": {
                "pause_count": int(stt_result.get("pause_count", 0) or 0),
                "avg_pause": float(stt_result.get("avg_pause", 0.0) or 0.0),
                "pauses": stt_result.get("pauses", []),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - error path is straightforward
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        try:
            file.file.close()
        except Exception:
            pass
        if temp_path.exists():
            temp_path.unlink()
