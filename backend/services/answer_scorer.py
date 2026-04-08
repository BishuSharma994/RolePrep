from __future__ import annotations

from collections import Counter

from backend.services.answer_analysis_types import (
    AnswerAnalysisRequest,
    AnswerStructure,
    ExtractedSignals,
    ScoreBreakdown,
    ScoreDetail,
    SentenceFailure,
    StructuredSentence,
)


def _clamp_score(score: int) -> int:
    return max(0, min(25, int(score)))


def _issue_counts(failures: list[SentenceFailure] | None) -> Counter[str]:
    counts: Counter[str] = Counter()
    for failure in failures or []:
        for issue in failure.issues:
            counts[issue.type] += 1
    return counts


def _voice_signals(context: AnswerAnalysisRequest) -> dict[str, int | float]:
    voice_signals = (context.parser_data or {}).get("voice_signals", {})
    if isinstance(voice_signals, dict):
        return voice_signals
    return {}


def score_structure(sentences: list[StructuredSentence], structure: AnswerStructure) -> ScoreDetail:
    if not sentences:
        return ScoreDetail(name="structure", score=0, reason="No usable answer structure.")

    score = 7
    reasons: list[str] = []

    if structure.intro_count:
        score += 4
    else:
        reasons.append("No opening frame.")

    if structure.body_count:
        score += 4
    else:
        reasons.append("No usable body.")

    if structure.example_count:
        score += 6
    else:
        reasons.append("No concrete example.")

    if structure.conclusion_count:
        score += 4
    else:
        reasons.append("No clear close.")

    if len(sentences) >= 2:
        score += 2
    else:
        reasons.append("One sentence is not enough to defend the answer.")

    if any(not sentence.ends_cleanly for sentence in sentences):
        score -= 2
        reasons.append("Sentence control is sloppy.")

    return ScoreDetail(
        name="structure",
        score=_clamp_score(score),
        reason=" ".join(reasons) if reasons else "Structure is finally doing its job.",
    )


def score_specificity(signals: ExtractedSignals, failures: list[SentenceFailure] | None = None) -> ScoreDetail:
    issue_counts = _issue_counts(failures)
    score = 25
    reasons: list[str] = []

    if signals.metric_count == 0 or issue_counts["no_metric"] > 0:
        score -= 10
        reasons.append("No measurable proof.")
    elif signals.metric_count >= 2:
        score += 1

    if issue_counts["vague"] > 0:
        score -= min(8, issue_counts["vague"] * 4)
        reasons.append("Vague wording weakens the claim.")

    if issue_counts["weak_ownership"] > 0:
        score -= min(8, issue_counts["weak_ownership"] * 6)
        reasons.append("Ownership is still unclear.")
    elif signals.ownership_strength == "strong":
        score += 1

    if issue_counts["no_impact"] > 0:
        score -= min(6, issue_counts["no_impact"] * 4)
        reasons.append("Action appears without outcome.")
    elif signals.impact_count > 0:
        score += 1

    if signals.tools:
        score += min(2, len(signals.tools))

    return ScoreDetail(
        name="specificity",
        score=_clamp_score(score),
        reason=" ".join(reasons) if reasons else "Specificity is carrying the answer.",
    )


def score_clarity(
    sentences: list[StructuredSentence],
    signals: ExtractedSignals,
    failures: list[SentenceFailure] | None = None,
) -> ScoreDetail:
    issue_counts = _issue_counts(failures)
    score = 22
    reasons: list[str] = []

    if issue_counts["filler"] > 0 or signals.filler_count > 0:
        score -= min(8, max(issue_counts["filler"], signals.filler_count) * 2)
        reasons.append("Filler language drags the answer down.")

    long_sentences = sum(1 for sentence in sentences if sentence.token_count > 35)
    if long_sentences:
        score -= min(6, long_sentences * 3)
        reasons.append("At least one sentence runs too long.")

    if any(sentence.starts_with_connector for sentence in sentences[1:]):
        score -= 2
        reasons.append("The answer sounds stitched together.")

    if any(not sentence.ends_cleanly for sentence in sentences):
        score -= 2
        reasons.append("Some thoughts end badly.")

    if len(sentences) == 1 and sentences[0].token_count < 10:
        score -= 4
        reasons.append("The answer is too thin to be clear.")

    return ScoreDetail(
        name="clarity",
        score=_clamp_score(score),
        reason=" ".join(reasons) if reasons else "Clarity is not the problem here.",
    )


def score_relevance(signals: ExtractedSignals, context: AnswerAnalysisRequest) -> ScoreDetail:
    score = round((signals.overall_relevance_score * 18) + 7)
    reasons: list[str] = []

    if signals.overall_relevance_score < 0.35:
        reasons.append("The answer dodges the question.")
    elif signals.overall_relevance_score < 0.6:
        reasons.append("The answer only partially addresses the prompt.")

    if not context.current_question.strip():
        reasons.append("Question context was missing.")

    return ScoreDetail(
        name="relevance",
        score=_clamp_score(score),
        reason=" ".join(reasons) if reasons else "Relevance is holding up.",
    )


def score_delivery(context: AnswerAnalysisRequest, failures: list[SentenceFailure] | None = None) -> ScoreDetail:
    voice_signals = _voice_signals(context)
    issue_counts = _issue_counts(failures)
    score = 25
    reasons: list[str] = []

    filler_count = int(voice_signals.get("filler_count", 0) or 0)
    if filler_count > 3 or issue_counts["too_many_fillers"] > 0:
        score -= 5
        reasons.append("Too many fillers weaken delivery.")

    long_pauses = int(voice_signals.get("long_pauses", 0) or 0)
    if long_pauses > 2 or issue_counts["long_pauses"] > 0:
        score -= 5
        reasons.append("Long pauses break momentum.")

    speech_rate = float(voice_signals.get("speech_rate", 0.0) or 0.0)
    if 0.0 < speech_rate < 1.5 or issue_counts["low_speech_rate"] > 0:
        score -= 5
        reasons.append("Speech rate is too slow.")

    return ScoreDetail(
        name="delivery",
        score=_clamp_score(score),
        reason=" ".join(reasons) if reasons else "Delivery supports the answer.",
    )


def score_answer(
    sentences: list[StructuredSentence],
    structure: AnswerStructure,
    signals: ExtractedSignals,
    context: AnswerAnalysisRequest,
    failures: list[SentenceFailure] | None = None,
) -> ScoreBreakdown:
    structure_score = score_structure(sentences, structure)
    specificity_score = score_specificity(signals, failures=failures)
    clarity_score = score_clarity(sentences, signals, failures=failures)
    relevance_score = score_relevance(signals, context)
    delivery_score = score_delivery(context, failures=failures)
    content_score = structure_score.score + specificity_score.score + clarity_score.score + relevance_score.score
    normalized_content_score = round((content_score / 100) * 75)
    total = normalized_content_score + delivery_score.score

    return ScoreBreakdown(
        structure=structure_score,
        specificity=specificity_score,
        clarity=clarity_score,
        relevance=relevance_score,
        delivery=delivery_score,
        total=max(0, min(100, total)),
    )


def map_score_100_to_legacy_10(total_score: int | float, answer_text: str = "") -> float:
    if not str(answer_text or "").strip():
        return 0.0
    mapped = round(float(total_score) / 10.0, 1)
    return max(1.0, min(10.0, mapped))
