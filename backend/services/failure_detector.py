from __future__ import annotations

from backend.services.answer_analysis_types import (
    ExtractedSignals,
    ScoreBreakdown,
    SentenceFailure,
    SentenceIssue,
    SentenceSignals,
    StructuredSentence,
)

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
_OWNERSHIP_HELPER_PHRASES = {"helped", "worked on", "supported", "participated in", "involved in"}


def _sentence_signal_map(signals: ExtractedSignals) -> dict[int, SentenceSignals]:
    return {signal.sentence_index: signal for signal in signals.sentence_signals}


def _build_issue(issue_type: str, reason: str, severity: str, fix: str) -> SentenceIssue:
    return SentenceIssue(type=issue_type, reason=reason, severity=severity, fix=fix)


def _join_phrases(phrases: list[str]) -> str:
    unique: list[str] = []
    for phrase in phrases:
        if phrase not in unique:
            unique.append(phrase)
    return ", ".join(f"'{phrase}'" for phrase in unique)


def _has_action_claim(sentence: StructuredSentence, sentence_signals: SentenceSignals) -> bool:
    ownership = sentence_signals.ownership
    if ownership and ownership.personal_action_verbs > 0:
        return True
    if sentence_signals.vague_phrases:
        return True
    if sentence_signals.impacts:
        return True
    lowered = sentence.text.lower()
    return any(
        keyword in lowered
        for keyword in ("built", "designed", "implemented", "improved", "reduced", "created", "led", "owned", "managed")
    )


def _detect_vague_issue(sentence_signals: SentenceSignals) -> SentenceIssue | None:
    if not sentence_signals.vague_phrases:
        return None
    phrases = [signal.phrase for signal in sentence_signals.vague_phrases]
    severity = "high" if len(phrases) >= 2 else "medium"
    return _build_issue(
        "vague",
        f"Vague wording {_join_phrases(phrases)} says nothing concrete. This sounds like resume fog, not evidence.",
        severity,
        "Replace each vague verb with the exact action, decision, or deliverable you personally drove.",
    )


def _detect_ownership_issue(sentence_signals: SentenceSignals) -> SentenceIssue | None:
    ownership = sentence_signals.ownership
    if ownership is None:
        return _build_issue(
            "weak_ownership",
            "No ownership signal exists. The sentence hides who did the work.",
            "high",
            "State your exact role, your decision, and your accountable action.",
        )

    helper_phrases = [signal.phrase for signal in sentence_signals.vague_phrases if signal.phrase in _OWNERSHIP_HELPER_PHRASES]
    if ownership.level == "strong":
        return None
    if ownership.level == "mixed" and ownership.personal_action_verbs > 0:
        return None
    if ownership.level == "mixed":
        return _build_issue(
            "weak_ownership",
            "Ownership is split between 'I' and team language. The interviewer still cannot isolate your contribution.",
            "high",
            "Separate your work from the team's and name the piece you personally owned.",
        )
    if ownership.level == "weak" and helper_phrases:
        return _build_issue(
            "weak_ownership",
            f"Vague ownership verb {_join_phrases(helper_phrases)} hides responsibility. The sentence still avoids accountability.",
            "high",
            "Replace helper language with a direct ownership statement and the exact action you took.",
        )
    if ownership.level == "weak":
        return _build_issue(
            "weak_ownership",
            "The sentence leans on team language and never proves personal ownership.",
            "high",
            "Name what you owned instead of hiding behind 'we' or passive contribution language.",
        )
    return _build_issue(
        "weak_ownership",
        "No personal ownership appears anywhere in the sentence. This is evasive.",
        "high",
        "Add the first-person action that shows what you did, not what the team did.",
    )


def _detect_metric_issue(sentence: StructuredSentence, sentence_signals: SentenceSignals, overall_signals: ExtractedSignals) -> SentenceIssue | None:
    if sentence_signals.metrics:
        return None
    has_action_claim = _has_action_claim(sentence, sentence_signals)
    if not has_action_claim and overall_signals.metric_count > 0:
        return None
    if sentence.token_count <= 4 and not sentence_signals.impacts:
        return None
    if overall_signals.metric_count > 0 and sentence.section == "intro" and not sentence_signals.impacts:
        return None
    if overall_signals.metric_count > 0 and sentence_signals.impacts:
        return None
    if overall_signals.metric_count > 0 and sentence.section != "example":
        return None
    return _build_issue(
        "no_metric",
        "No measurable outcome. This fails credibility.",
        "high",
        "Add numbers, percentages, scale, latency, volume, or time saved.",
    )


def _detect_impact_issue(sentence: StructuredSentence, sentence_signals: SentenceSignals) -> SentenceIssue | None:
    if sentence_signals.impacts:
        return None
    if not _has_action_claim(sentence, sentence_signals):
        return None
    return _build_issue(
        "no_impact",
        "The sentence reports activity and stops there. No outcome, no consequence, no case made.",
        "high",
        "Finish the sentence with the business or technical result your action produced.",
    )


def _detect_filler_issue(sentence_signals: SentenceSignals) -> SentenceIssue | None:
    if not sentence_signals.fillers:
        return None
    phrases = [signal.phrase for signal in sentence_signals.fillers]
    count = sum(signal.count for signal in sentence_signals.fillers)
    severity = "medium" if count >= 2 else "low"
    return _build_issue(
        "filler",
        f"Filler language {_join_phrases(phrases)} adds noise instead of proof.",
        severity,
        "Delete the filler and state the point in one hard, direct sentence.",
    )


def _voice_signals_from_context(context) -> dict[str, int | float]:
    parser_data = getattr(context, "parser_data", {}) or {}
    voice_signals = parser_data.get("voice_signals", {})
    if isinstance(voice_signals, dict):
        return voice_signals
    return {}


def _build_voice_issues(context) -> list[SentenceIssue]:
    voice_signals = _voice_signals_from_context(context)
    issues: list[SentenceIssue] = []

    filler_count = int(voice_signals.get("filler_count", 0) or 0)
    if filler_count > 3:
        issues.append(
            _build_issue(
                "too_many_fillers",
                f"Delivery is cluttered with {filler_count} filler words. The answer sounds hesitant instead of controlled.",
                "medium",
                "Cut filler phrases and pause silently before the next point.",
            )
        )

    speech_rate = float(voice_signals.get("speech_rate", 0.0) or 0.0)
    if 0.0 < speech_rate < 1.5:
        issues.append(
            _build_issue(
                "low_speech_rate",
                f"Speech rate is only {speech_rate:.2f} words per second. The delivery drags and loses force.",
                "medium",
                "Tighten the answer and keep a steadier pace through the core example.",
            )
        )

    long_pauses = int(voice_signals.get("long_pauses", 0) or 0)
    if long_pauses > 2:
        issues.append(
            _build_issue(
                "long_pauses",
                f"There are {long_pauses} long pauses over 1.2 seconds. The delivery sounds uncertain.",
                "medium",
                "Shorten dead air and group ideas into fewer, cleaner beats.",
            )
        )

    return issues


def detect_failures(
    sentences: list[StructuredSentence],
    signals: ExtractedSignals,
    scores: ScoreBreakdown | None = None,
    context=None,
) -> list[SentenceFailure]:
    failures: list[SentenceFailure] = []
    sentence_signals_map = _sentence_signal_map(signals)

    for sentence in sentences:
        sentence_signals = sentence_signals_map.get(sentence.index, SentenceSignals(sentence_index=sentence.index))
        issues: list[SentenceIssue] = []

        for detector in (
            _detect_vague_issue,
            _detect_ownership_issue,
            lambda item: _detect_metric_issue(sentence, item, signals),
            lambda item: _detect_impact_issue(sentence, item),
            _detect_filler_issue,
        ):
            issue = detector(sentence_signals)
            if issue is not None:
                issues.append(issue)

        if sentence.index == 0:
            issues.extend(_build_voice_issues(context))

        failures.append(
            SentenceFailure(
                sentence=sentence.text,
                sentence_index=sentence.index,
                issues=issues,
            )
        )

    _ = scores, context
    return failures


def build_feedback_summary(failures: list[SentenceFailure], scores: ScoreBreakdown) -> str:
    ranked_issues: list[SentenceIssue] = []
    for failure in failures:
        ranked_issues.extend(failure.issues)
    ranked_issues.sort(key=lambda issue: (_SEVERITY_RANK.get(issue.severity, 3), issue.type))

    if ranked_issues:
        top_reasons: list[str] = []
        for issue in ranked_issues:
            if issue.reason not in top_reasons:
                top_reasons.append(issue.reason)
            if len(top_reasons) == 3:
                break
        return "Rejected answer. " + " ".join(top_reasons)

    if scores.total >= 85:
        return "Finally credible. Structure, ownership, and evidence are doing the work."
    return "Still not convincing. The answer avoids obvious defects but does not land evaluator-grade proof."
