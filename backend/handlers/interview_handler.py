from backend.services.plan_manager import (
    can_start_session,
    increment_usage,
    can_ask_question,
)

# session store (separate from engine)
SESSIONS = {}


def start_interview(user_id: str):
    if not can_start_session(user_id):
        return {
            "status": "blocked",
            "reason": "daily_limit_reached"
        }

    increment_usage(user_id)

    SESSIONS[user_id] = {
        "question_count": 0
    }

    return {
        "status": "started"
    }


def handle_next_question(user_id: str, engine_fn):
    session = SESSIONS.get(user_id)

    if not session:
        return {
            "status": "error",
            "reason": "no_active_session"
        }

    current_q_count = session.get("question_count", 0)

    if not can_ask_question(user_id, current_q_count):
        return {
            "status": "blocked",
            "reason": "question_limit_reached"
        }

    # ENGINE CALL (UNCHANGED)
    response = engine_fn()

    session["question_count"] = current_q_count + 1

    return {
        "status": "ok",
        "data": response
    }


def end_session(user_id: str):
    if user_id in SESSIONS:
        del SESSIONS[user_id]

    return {"status": "ended"}