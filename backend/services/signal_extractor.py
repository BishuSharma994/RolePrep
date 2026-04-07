from __future__ import annotations

import re

from backend.services.answer_analysis_types import (
    ExtractedSignals,
    FillerSignal,
    MetricSignal,
    OwnershipSignal,
    RelevanceSignal,
    SentenceSignals,
    StructuredSentence,
    ToolSignal,
    VaguenessSignal,
)
from backend.services.impact_signal_extractor import extract_impact_signals

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "i",
    "in",
    "into",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "there",
    "they",
    "this",
    "to",
    "was",
    "we",
    "with",
    "you",
}
_METRIC_PATTERNS = {
    "percentage": re.compile(r"\b\d+(?:\.\d+)?\s*%"),
    "multiplier": re.compile(r"\b\d+(?:\.\d+)?\s*x\b", re.IGNORECASE),
    "time": re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:ms|milliseconds?|s|sec|seconds?|mins?|minutes?|hours?|days?|weeks?|months?|years?)\b",
        re.IGNORECASE,
    ),
    "volume": re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:users?|requests?|records?|tickets?|pipelines?|services?|queries?|deployments?)\b",
        re.IGNORECASE,
    ),
    "number": re.compile(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b"),
}
_VAGUE_PHRASES = (
    "helped",
    "worked on",
    "handled",
    "supported",
    "participated in",
    "involved in",
    "responsible for",
    "looked after",
)
_HELPER_OWNERSHIP_PHRASES = {"helped", "worked on", "supported", "participated in", "involved in"}
_FILLER_PHRASES = (
    "basically",
    "actually",
    "kind of",
    "sort of",
    "you know",
    "like",
)
_KNOWN_TOOLS = {
    "airflow",
    "aws",
    "azure",
    "bigquery",
    "c++",
    "docker",
    "excel",
    "fastapi",
    "flask",
    "gcp",
    "git",
    "java",
    "javascript",
    "kafka",
    "kubernetes",
    "linux",
    "machine learning",
    "mongodb",
    "mysql",
    "pandas",
    "postgres",
    "postgresql",
    "power bi",
    "python",
    "pytorch",
    "redis",
    "spark",
    "sql",
    "tableau",
    "tensorflow",
}
_PERSONAL_ACTION_PATTERN = re.compile(
    r"\bi\s+(?:built|designed|implemented|led|owned|created|drove|reduced|improved|fixed|automated|migrated|optimized|launched|delivered|wrote|analyzed|proposed|decided|managed|resolved|rewrote|cut|eliminated|removed|added|shipped)\b",
    re.IGNORECASE,
)
_PERSONAL_PRONOUN_PATTERN = re.compile(r"\b(i|my|mine)\b", re.IGNORECASE)
_TEAM_REFERENCE_PATTERN = re.compile(r"\b(we|our|ours|team)\b", re.IGNORECASE)
_TOKEN_PATTERN = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+#.-]*\b")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(text or "")]


def _meaningful_terms(text: str) -> set[str]:
    return {token for token in _tokenize(text) if token not in _STOP_WORDS and len(token) > 2}


def _candidate_tools(parser_data: dict | None) -> set[str]:
    candidates = set(_KNOWN_TOOLS)
    if not parser_data:
        return candidates

    for section in ("resume", "jd"):
        values = parser_data.get(section, {})
        if not isinstance(values, dict):
            continue
        for key in ("skills", "keywords", "requirements"):
            items = values.get(key, [])
            if not isinstance(items, list):
                continue
            for item in items:
                item_text = str(item or "").strip().lower()
                if not item_text:
                    continue
                if len(item_text.split()) <= 3:
                    candidates.add(item_text)
                for token in _tokenize(item_text):
                    if len(token) > 2:
                        candidates.add(token)
    return candidates


def extract_metrics(text: str, sentence_index: int) -> list[MetricSignal]:
    metrics: list[MetricSignal] = []
    for kind, pattern in _METRIC_PATTERNS.items():
        for match in pattern.finditer(text or ""):
            metrics.append(MetricSignal(sentence_index=sentence_index, value=match.group(0), kind=kind))
    deduped: dict[tuple[str, str], MetricSignal] = {}
    for metric in metrics:
        deduped[(metric.value.lower(), metric.kind)] = metric
    return list(deduped.values())


def extract_vague_phrases(text: str, sentence_index: int) -> list[VaguenessSignal]:
    lowered = (text or "").lower()
    found: list[VaguenessSignal] = []
    for phrase in _VAGUE_PHRASES:
        if phrase in lowered:
            found.append(VaguenessSignal(sentence_index=sentence_index, phrase=phrase))
    return found


def extract_ownership(text: str, sentence_index: int) -> OwnershipSignal:
    lowered = (text or "").lower()
    personal_pronouns = len(_PERSONAL_PRONOUN_PATTERN.findall(text or ""))
    personal_actions = len(_PERSONAL_ACTION_PATTERN.findall(text or ""))
    team_references = len(_TEAM_REFERENCE_PATTERN.findall(text or ""))
    helper_vague_count = sum(1 for phrase in _HELPER_OWNERSHIP_PHRASES if phrase in lowered)

    if personal_actions > 0 and team_references == 0:
        level = "strong"
    elif personal_actions > 0 and team_references > 0:
        level = "mixed"
    elif personal_pronouns > 0 and team_references > 0:
        level = "mixed"
    elif team_references > 0:
        level = "weak"
    elif personal_pronouns > 0 and (helper_vague_count > 0 or personal_actions == 0):
        level = "weak"
    elif personal_pronouns > 0:
        level = "strong"
    else:
        level = "none"

    return OwnershipSignal(
        sentence_index=sentence_index,
        level=level,
        personal_pronouns=personal_pronouns,
        personal_action_verbs=personal_actions,
        team_references=team_references,
    )


def extract_tools(text: str, sentence_index: int, parser_data: dict | None = None) -> list[ToolSignal]:
    lowered = (text or "").lower()
    tools: list[ToolSignal] = []
    for candidate in sorted(_candidate_tools(parser_data), key=len, reverse=True):
        if len(candidate) < 2:
            continue
        pattern = rf"(?<!\w){re.escape(candidate)}(?!\w)"
        if re.search(pattern, lowered):
            source = "catalog"
            if parser_data:
                source = "catalog+profile"
            tools.append(ToolSignal(sentence_index=sentence_index, tool=candidate, source=source))
    deduped: dict[str, ToolSignal] = {}
    for tool in tools:
        deduped[tool.tool] = tool
    return list(deduped.values())


def extract_fillers(text: str, sentence_index: int) -> list[FillerSignal]:
    lowered = (text or "").lower()
    signals: list[FillerSignal] = []
    for phrase in _FILLER_PHRASES:
        count = lowered.count(phrase)
        if count > 0:
            signals.append(FillerSignal(sentence_index=sentence_index, phrase=phrase, count=count))
    return signals


def extract_relevance(text: str, sentence_index: int, current_question: str, jd_text: str) -> RelevanceSignal:
    sentence_terms = _meaningful_terms(text)
    question_terms = _meaningful_terms(current_question)
    jd_terms = _meaningful_terms(jd_text)

    matched_question = sorted(sentence_terms & question_terms)
    matched_jd = sorted(sentence_terms & jd_terms)
    direct_answer = bool(matched_question) or sentence_index == 0

    question_component = 1.0 if not question_terms else min(1.0, len(matched_question) / max(1, len(question_terms) / 3))
    jd_component = 0.0 if not jd_terms else min(1.0, len(matched_jd) / max(1, len(jd_terms) / 12))
    direct_component = 1.0 if direct_answer else 0.0
    score = round((question_component * 0.6) + (jd_component * 0.25) + (direct_component * 0.15), 2)

    return RelevanceSignal(
        sentence_index=sentence_index,
        matched_question_terms=matched_question,
        matched_jd_terms=matched_jd[:8],
        direct_answer=direct_answer,
        score=score,
    )


def _overall_ownership_strength(signals: list[OwnershipSignal]) -> str:
    levels = {signal.level for signal in signals}
    if "mixed" in levels:
        return "mixed"
    if "weak" in levels and "strong" in levels:
        return "mixed"
    if "weak" in levels:
        return "weak"
    if "strong" in levels:
        return "strong"
    return "none"


def extract_signals(
    answer_text: str,
    sentences: list[StructuredSentence],
    current_question: str,
    jd_text: str,
    parser_data: dict | None = None,
) -> ExtractedSignals:
    all_metrics: list[MetricSignal] = []
    all_impacts = []
    all_vague: list[VaguenessSignal] = []
    all_ownership: list[OwnershipSignal] = []
    all_tools: list[ToolSignal] = []
    all_fillers: list[FillerSignal] = []
    all_relevance: list[RelevanceSignal] = []
    sentence_signals: list[SentenceSignals] = []

    for sentence in sentences:
        metrics = extract_metrics(sentence.text, sentence.index)
        impacts = extract_impact_signals(sentence.text, sentence.index)
        vague = extract_vague_phrases(sentence.text, sentence.index)
        ownership = extract_ownership(sentence.text, sentence.index)
        tools = extract_tools(sentence.text, sentence.index, parser_data=parser_data)
        fillers = extract_fillers(sentence.text, sentence.index)
        relevance = extract_relevance(sentence.text, sentence.index, current_question, jd_text)

        all_metrics.extend(metrics)
        all_impacts.extend(impacts)
        all_vague.extend(vague)
        all_ownership.append(ownership)
        all_tools.extend(tools)
        all_fillers.extend(fillers)
        all_relevance.append(relevance)

        sentence_signals.append(
            SentenceSignals(
                sentence_index=sentence.index,
                metrics=metrics,
                impacts=impacts,
                vague_phrases=vague,
                ownership=ownership,
                tools=tools,
                fillers=fillers,
                relevance=relevance,
            )
        )

    if all_relevance:
        average_relevance = sum(signal.score for signal in all_relevance) / len(all_relevance)
        best_relevance = max(signal.score for signal in all_relevance)
        first_relevance = all_relevance[0].score
        overall_relevance = round(
            (average_relevance * 0.5) + (best_relevance * 0.3) + (first_relevance * 0.2),
            2,
        )
    else:
        overall_relevance = 0.0

    _ = answer_text
    return ExtractedSignals(
        sentence_signals=sentence_signals,
        metrics=all_metrics,
        impacts=all_impacts,
        vague_phrases=all_vague,
        ownership=all_ownership,
        tools=all_tools,
        fillers=all_fillers,
        relevance=all_relevance,
        metric_count=len(all_metrics),
        impact_count=len(all_impacts),
        vague_phrase_count=len(all_vague),
        filler_count=sum(signal.count for signal in all_fillers),
        ownership_strength=_overall_ownership_strength(all_ownership),
        overall_relevance_score=overall_relevance,
    )
