from backend.services.plan_manager import can_ask_question, can_start_session, increment_usage

SESSIONS = {}


def start_interview(user_id: str, role: str, jd_text: str):
    if not can_start_session(user_id):
        return {"status": "blocked", "reason": "daily_limit_reached"}

    increment_usage(user_id)

    SESSIONS[user_id] = {
        "role": role,
        "jd_text": jd_text,
        "history": [],
        "scores": [],
        "question_count": 0,
        "pending_answer": None,
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
        return {"status": "blocked", "reason": "question_limit_reached"}

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
        del SESSIONS[user_id]

    return {"status": "ended"}
