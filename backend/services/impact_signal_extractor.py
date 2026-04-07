from __future__ import annotations

import re

from backend.services.answer_analysis_types import ImpactSignal

_CONNECTOR_PHRASES = (
    "as a result",
    "resulted in",
    "resulting in",
    "led to",
    "which led to",
    "thereby",
    "so that",
    "this caused",
    "the outcome was",
    "the result was",
)
_RESULT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "result_verb",
        re.compile(
            r"\b(increased|improved|reduced|cut|saved|eliminated|prevented|accelerated|boosted|grew|stabilized|streamlined|lowered)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "impact_noun",
        re.compile(
            r"\b(impact|outcome|efficiency|latency|throughput|reliability|cost|revenue|conversion|tickets|incidents|errors|failures|quality|uptime)\b",
            re.IGNORECASE,
        ),
    ),
)


def extract_impact_signals(text: str, sentence_index: int) -> list[ImpactSignal]:
    lowered = str(text or "").lower()
    impacts: list[ImpactSignal] = []

    for phrase in _CONNECTOR_PHRASES:
        if phrase in lowered:
            impacts.append(ImpactSignal(sentence_index=sentence_index, phrase=phrase, kind="connector"))

    for kind, pattern in _RESULT_PATTERNS:
        for match in pattern.finditer(text or ""):
            impacts.append(ImpactSignal(sentence_index=sentence_index, phrase=match.group(0), kind=kind))

    deduped: dict[tuple[str, str], ImpactSignal] = {}
    for impact in impacts:
        deduped[(impact.phrase.lower(), impact.kind)] = impact
    return list(deduped.values())
