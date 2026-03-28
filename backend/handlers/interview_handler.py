import os

from backend.handlers.payment_handler import handle_payment_request
from backend.services.plan_manager import can_ask_question, can_start_session, increment_usage

SESSIONS = {}


def cleanup_session_files(session: dict):
    for key in ("resume_path", "jd_path"):
        file_path = session.get(key)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


def start_interview(
    user_id: str,
    role: str,
    jd_text: str,
    parser_data: dict | None = None,
    resume_path: str | None = None,
    jd_path: str | None = None,
):
    if not can_start_session(user_id):
        return handle_payment_request(user_id, "session")

    increment_usage(user_id)

    SESSIONS[user_id] = {
        "role": role,
        "jd_text": jd_text,
        "history": [],
        "scores": [],
        "question_count": 0,
        "pending_answer": None,
        "parser_data": parser_data or {},
        "resume_path": resume_path,
        "jd_path": jd_path,
    }

    return {"status": "started"}


def get_session(user_id: str):
    return SESSIONS.get(user_id)


def set_pending_answer(user_id: str, user_input: str) -> bool:
    session = SESSIONS.get(user_id)
    if not session:
        return False

    session["pending_answer"] = user_input
    return True


def handle_next_question(user_id: str, engine_fn):
    session = SESSIONS.get(user_id)
    if not session:
        return {"status": "error", "reason": "no_active_session"}

    current_q_count = session.get("question_count", 0)
    if not can_ask_question(user_id, current_q_count):
        return handle_payment_request(user_id, "session")

    pending_answer = session.get("pending_answer")
    if pending_answer is None:
        return {"status": "error", "reason": "no_pending_answer"}

    response = engine_fn(
        role=session["role"],
        jd_text=session["jd_text"],
        user_input=pending_answer,
        session=session,
    )

    session["question_count"] = current_q_count + 1
    session["history"].append(pending_answer)
    session["scores"].append(response.get("score", 0))
    session["pending_answer"] = None

    return {"status": "ok", "data": response}


def end_session(user_id: str):
    if user_id in SESSIONS:
        cleanup_session_files(SESSIONS[user_id])
        del SESSIONS[user_id]

    return {"status": "ended"}
