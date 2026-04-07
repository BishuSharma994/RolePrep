from __future__ import annotations

from backend.services.answer_analysis_types import AnswerAnalysisRequest, AnswerAnalysisResult
from backend.services.answer_parser import parse_answer
from backend.services.answer_scorer import map_score_100_to_legacy_10, score_answer
from backend.services.failure_detector import build_feedback_summary, detect_failures
from backend.services.followup_generator import generate_followup
from backend.services.signal_extractor import extract_signals


def _build_compat_response(result: AnswerAnalysisResult) -> dict[str, object]:
    return {
        "score": result.legacy_score_10,
        "feedback": result.feedback_summary,
        "next_question": result.next_question,
        "analysis": result.to_dict(),
    }


def analyze_answer(request: AnswerAnalysisRequest) -> AnswerAnalysisResult:
    parsed_sentences, answer_structure = parse_answer(request.answer_text)
    signals = extract_signals(
        answer_text=request.answer_text,
        sentences=parsed_sentences,
        current_question=request.current_question,
        jd_text=request.jd_text,
        parser_data=request.parser_data,
    )
    failures = detect_failures(parsed_sentences, signals, context=request)
    scores = score_answer(parsed_sentences, answer_structure, signals, request, failures=failures)
    followup = generate_followup(parsed_sentences, signals, scores, failures, request)
    feedback_summary = build_feedback_summary(failures, scores)
    overall_score_100 = scores.total
    legacy_score_10 = map_score_100_to_legacy_10(overall_score_100, request.answer_text)

    result = AnswerAnalysisResult(
        parsed_sentences=parsed_sentences,
        answer_structure=answer_structure,
        signals=signals,
        scores=scores,
        failures=failures,
        followup=followup,
        feedback_summary=feedback_summary,
        overall_score_100=overall_score_100,
        legacy_score_10=legacy_score_10,
        next_question=followup.question,
        compat_response={},
    )
    result.compat_response = _build_compat_response(result)
    return result
