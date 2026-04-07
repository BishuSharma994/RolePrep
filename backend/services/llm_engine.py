from __future__ import annotations

from backend.services.answer_analysis_types import AnswerAnalysisRequest
from backend.services.answer_failure_engine import analyze_answer


def generate_response(role, jd_text, user_input, session=None):
    session = session or {}
    request = AnswerAnalysisRequest(
        role=str(role or ""),
        jd_text=str(jd_text or ""),
        current_question=str(session.get("current_question") or ""),
        answer_text=str(user_input or ""),
        session_history=[str(item) for item in session.get("history", [])[-5:]],
        parser_data=session.get("parser_data") or {},
    )
    result = analyze_answer(request)
    return result.compat_response
