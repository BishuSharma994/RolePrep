from __future__ import annotations

import re
from typing import Any

_FILLER_WORDS = ("um", "uh", "like", "you know", "basically", "actually")


def _count_fillers(transcript: str) -> int:
    lowered = str(transcript or "").lower()
    total = 0
    for phrase in _FILLER_WORDS:
        pattern = rf"(?<!\w){re.escape(phrase)}(?!\w)"
        total += len(re.findall(pattern, lowered))
    return total


def extract_voice_signals(segments: list[dict[str, Any]], transcript: str) -> dict[str, int | float]:
    filler_count = _count_fillers(transcript)
    total_words = len(str(transcript or "").split())

    audio_duration = 0.0
    if segments:
        try:
            audio_duration = max(float(segments[-1].get("end", 0.0) or 0.0), 0.0)
        except (AttributeError, TypeError, ValueError):
            audio_duration = 0.0

    speech_rate = round(total_words / audio_duration, 2) if audio_duration > 0 else 0.0

    long_pauses = 0
    for current, following in zip(segments, segments[1:]):
        try:
            pause = float(following.get("start", 0.0) or 0.0) - float(current.get("end", 0.0) or 0.0)
        except (AttributeError, TypeError, ValueError):
            pause = 0.0
        if pause > 1.2:
            long_pauses += 1

    return {
        "filler_count": int(filler_count),
        "speech_rate": float(speech_rate),
        "long_pauses": int(long_pauses),
    }
