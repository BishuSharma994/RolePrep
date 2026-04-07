from __future__ import annotations

from backend.services.answer_analysis_types import (
    AnswerAnalysisRequest,
    ExtractedSignals,
    FollowupDecision,
    ScoreBreakdown,
    SentenceFailure,
    StructuredSentence,
)


def _flatten_issue_types(failures: list[SentenceFailure]) -> set[str]:
    issue_types: set[str] = set()
    for failure in failures:
        for issue in failure.issues:
            issue_types.add(issue.type)
    return issue_types


def _has_weak_ownership(signals: ExtractedSignals) -> bool:
    return any(
        signal.level in {"weak", "none"} or (signal.level == "mixed" and signal.personal_action_verbs == 0)
        for signal in signals.ownership
    )


def _priority(triggered_by: list[str]) -> int:
    ranking = {
        "no_metric": 1,
        "weak_ownership": 2,
        "vague": 3,
        "no_impact": 4,
        "filler": 5,
        "depth": 6,
    }
    return min((ranking.get(item, 9) for item in triggered_by), default=6)


def generate_followup(
    sentences: list[StructuredSentence],
    signals: ExtractedSignals,
    scores: ScoreBreakdown,
    failures: list[SentenceFailure],
    context: AnswerAnalysisRequest,
) -> FollowupDecision:
    _ = sentences, scores, context
    failure_issue_types = _flatten_issue_types(failures)
    triggered_by: list[str] = []
    prompts: list[str] = []

    if signals.metric_count == 0:
        triggered_by.append("no_metric")
        prompts.append("What changed in measurable terms? Give numbers, percentages, scale, or time saved.")

    if signals.vague_phrase_count > 0 or "vague" in failure_issue_types:
        triggered_by.append("vague")
        prompts.append("Stop hiding behind generic verbs. State the exact action you took.")

    if _has_weak_ownership(signals) or "weak_ownership" in failure_issue_types:
        triggered_by.append("weak_ownership")
        prompts.append("Separate your work from the team's. What did you personally own?")

    if signals.impact_count == 0 or "no_impact" in failure_issue_types:
        triggered_by.append("no_impact")
        prompts.append("Finish the story. What business or technical outcome did your action create?")

    if not triggered_by:
        triggered_by.append("depth")
        prompts.append("Defend the trade-offs. Why was your approach the right call?")

    unique_triggers: list[str] = []
    for item in triggered_by:
        if item not in unique_triggers:
            unique_triggers.append(item)

    unique_prompts: list[str] = []
    for prompt in prompts:
        if prompt not in unique_prompts:
            unique_prompts.append(prompt)

    reason = "Triggered by " + ", ".join(unique_triggers) + "."
    return FollowupDecision(
        question=" ".join(unique_prompts),
        reason=reason,
        triggered_by=unique_triggers,
        priority=_priority(unique_triggers),
    )
