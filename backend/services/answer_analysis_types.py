from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def to_serializable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [to_serializable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_serializable(item) for key, item in value.items()}
    return value


@dataclass(slots=True)
class AnswerAnalysisRequest:
    role: str
    jd_text: str
    current_question: str
    answer_text: str
    session_history: list[str] = field(default_factory=list)
    parser_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SentenceUnit:
    index: int
    text: str
    token_count: int
    starts_with_connector: bool
    ends_cleanly: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StructuredSentence:
    index: int
    text: str
    token_count: int
    starts_with_connector: bool
    ends_cleanly: bool
    section: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnswerStructure:
    intro_count: int = 0
    body_count: int = 0
    example_count: int = 0
    conclusion_count: int = 0
    unclassified_count: int = 0
    dominant_shape: str = "unstructured"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MetricSignal:
    sentence_index: int
    value: str
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ImpactSignal:
    sentence_index: int
    phrase: str
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class VaguenessSignal:
    sentence_index: int
    phrase: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OwnershipSignal:
    sentence_index: int
    level: str
    personal_pronouns: int
    personal_action_verbs: int
    team_references: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ToolSignal:
    sentence_index: int
    tool: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FillerSignal:
    sentence_index: int
    phrase: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RelevanceSignal:
    sentence_index: int
    matched_question_terms: list[str] = field(default_factory=list)
    matched_jd_terms: list[str] = field(default_factory=list)
    direct_answer: bool = False
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SentenceSignals:
    sentence_index: int
    metrics: list[MetricSignal] = field(default_factory=list)
    impacts: list[ImpactSignal] = field(default_factory=list)
    vague_phrases: list[VaguenessSignal] = field(default_factory=list)
    ownership: OwnershipSignal | None = None
    tools: list[ToolSignal] = field(default_factory=list)
    fillers: list[FillerSignal] = field(default_factory=list)
    relevance: RelevanceSignal | None = None

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(asdict(self))


@dataclass(slots=True)
class ExtractedSignals:
    sentence_signals: list[SentenceSignals] = field(default_factory=list)
    metrics: list[MetricSignal] = field(default_factory=list)
    impacts: list[ImpactSignal] = field(default_factory=list)
    vague_phrases: list[VaguenessSignal] = field(default_factory=list)
    ownership: list[OwnershipSignal] = field(default_factory=list)
    tools: list[ToolSignal] = field(default_factory=list)
    fillers: list[FillerSignal] = field(default_factory=list)
    relevance: list[RelevanceSignal] = field(default_factory=list)
    metric_count: int = 0
    impact_count: int = 0
    vague_phrase_count: int = 0
    filler_count: int = 0
    ownership_strength: str = "none"
    overall_relevance_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(asdict(self))


@dataclass(slots=True)
class ScoreDetail:
    name: str
    score: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScoreBreakdown:
    structure: ScoreDetail
    specificity: ScoreDetail
    clarity: ScoreDetail
    relevance: ScoreDetail
    delivery: ScoreDetail
    total: int

    def to_dict(self) -> dict[str, Any]:
        return to_serializable(asdict(self))


@dataclass(slots=True)
class SentenceIssue:
    type: str
    reason: str
    severity: str
    fix: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SentenceFailure:
    sentence: str
    sentence_index: int
    issues: list[SentenceIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sentence": self.sentence,
            "sentence_index": self.sentence_index,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(slots=True)
class FollowupDecision:
    question: str
    reason: str
    triggered_by: list[str] = field(default_factory=list)
    priority: int = 1
    type: str = "aggressive_probe"
    requires_stage_change: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnswerAnalysisResult:
    parsed_sentences: list[StructuredSentence]
    answer_structure: AnswerStructure
    signals: ExtractedSignals
    scores: ScoreBreakdown
    failures: list[SentenceFailure]
    followup: FollowupDecision
    feedback_summary: str
    overall_score_100: int
    legacy_score_10: float
    next_question: str
    compat_response: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "parsed_sentences": [sentence.to_dict() for sentence in self.parsed_sentences],
            "answer_structure": self.answer_structure.to_dict(),
            "signals": self.signals.to_dict(),
            "scores": self.scores.to_dict(),
            "failures": [failure.to_dict() for failure in self.failures],
            "followup": self.followup.to_dict(),
            "feedback_summary": self.feedback_summary,
            "overall_score_100": self.overall_score_100,
            "legacy_score_10": self.legacy_score_10,
            "next_question": self.next_question,
            "compat_response": dict(self.compat_response),
        }
