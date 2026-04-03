import os
import time
import uuid

from backend.services.db import users
from backend.services.session_state import clear_state, load_state, save_state
from backend.services.llm_engine import generate_response
from backend.user_store import (
    can_ask_question,
    can_start_session,
    complete_session,
    get_user,
    is_session_timed_out,
    release_active_session,
    set_bot_state,
    start_session,
    touch_active_session,
)

SESSIONS = {}


def run_interview_engine(role, jd_text, user_input, session):
    return generate_response(
        role=role,
        jd_text=jd_text,
        user_input=user_input,
        session=session,
    )


def cleanup_session_files(session: dict):
    for key in ("resume_path", "jd_path"):
        file_path = session.get(key)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


def _session_snapshot(session: dict) -> dict:
    return {
        "current_question": session.get("current_question"),
        "current_stage": session.get("current_stage"),
        "session_id": session.get("session_id"),
        "last_answer": session.get("last_answer"),
        "last_question_ts": session.get("last_question_ts"),
        "updated_at": time.time(),
        "session_role": session.get("role"),
        "session_jd_text": session.get("jd_text"),
        "session_history": list(session.get("history", [])),
        "session_scores": list(session.get("scores", [])),
        "session_question_count": int(session.get("question_count", 0) or 0),
        "session_parser_data": session.get("parser_data") or {},
        "session_resume_path": session.get("resume_path"),
        "session_jd_path": session.get("jd_path"),
        "session_pending_answer": session.get("pending_answer"),
        "anti_cheat_flags": session.get("anti_cheat_flags") or {},
        "pending_followup": session.get("pending_followup"),
    }


def _persist_session(user_id: str, session: dict):
    save_state(user_id, _session_snapshot(session))
    touch_active_session(user_id)


def _expire_session(user_id: str):
    session = SESSIONS.get(user_id) or _restore_session_from_state(user_id)
    if session:
        cleanup_session_files(session)
    if user_id in SESSIONS:
        del SESSIONS[user_id]
    clear_state(user_id)
    release_active_session(user_id)


def _restore_session_from_state(user_id: str):
    state = load_state(user_id)
    if not state.get("current_stage"):
        return None

    restored_session = {
        "role": state.get("session_role", ""),
        "jd_text": state.get("session_jd_text", ""),
        "history": list(state.get("session_history", [])),
        "scores": list(state.get("session_scores", [])),
        "question_count": int(state.get("session_question_count", 0) or 0),
        "pending_answer": state.get("session_pending_answer"),
        "parser_data": state.get("session_parser_data") or {},
        "resume_path": state.get("session_resume_path"),
        "jd_path": state.get("session_jd_path"),
        "current_question": state.get("current_question"),
        "current_stage": state.get("current_stage"),
        "session_id": state.get("session_id"),
        "last_answer": state.get("last_answer"),
        "last_question_ts": state.get("last_question_ts"),
        "anti_cheat_flags": state.get("anti_cheat_flags") or {},
        "pending_followup": state.get("pending_followup"),
    }

    if not restored_session["session_id"]:
        restored_session["session_id"] = uuid.uuid4().hex

    if not restored_session["role"] or not restored_session["jd_text"]:
        return None

    SESSIONS[user_id] = restored_session
    return restored_session


def start_interview(
    user_id: str,
    role: str,
    jd_text: str,
    parser_data: dict | None = None,
    resume_path: str | None = None,
    jd_path: str | None = None,
):
    user_id = str(user_id)

    if not can_start_session(user_id):
        return {"status": "blocked", "reason": "session_limit_reached"}

    if not start_session(user_id):
        return {"status": "blocked", "reason": "session_limit_reached"}

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
        "current_question": None,
        "current_stage": "interview",
        "session_id": uuid.uuid4().hex,
        "last_answer": None,
        "last_question_ts": None,
        "anti_cheat_flags": {},
        "pending_followup": None,
    }
    set_bot_state(user_id, "IN_INTERVIEW")
    _persist_session(user_id, SESSIONS[user_id])

    return {"status": "started", "session_id": SESSIONS[user_id]["session_id"]}


def get_session(user_id: str):
    user_id = str(user_id)
    user = get_user(user_id)
    if user.get("active_session") and is_session_timed_out(user_id):
        _expire_session(user_id)
        return None

    session = SESSIONS.get(user_id)
    if session:
        return session
    return _restore_session_from_state(user_id)


def save_session_checkpoint(user_id: str, **updates) -> bool:
    session = get_session(user_id)
    if not session:
        return False

    session.update(updates)
    _persist_session(user_id, session)
    return True


def record_question_sent(user_id: str, question: str, stage: str = "interview", **extra_updates) -> bool:
    updates = {
        "current_question": question,
        "current_stage": stage,
        "last_question_ts": time.time(),
        "pending_answer": None,
    }
    updates.update(extra_updates)
    return save_session_checkpoint(user_id, **updates)


def set_pending_answer(user_id: str, user_input: str) -> bool:
    session = get_session(user_id)
    if not session:
        return False

    session["pending_answer"] = user_input
    if session.get("current_stage") != "awaiting_followup":
        session["last_answer"] = user_input
    _persist_session(user_id, session)
    return True


def handle_next_question(user_id: str, engine_fn):
    session = get_session(user_id)
    if not session:
        return {"status": "error", "reason": "no_active_session"}

    current_q_count = session.get("question_count", 0)
    if not can_ask_question(user_id):
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
    _persist_session(user_id, session)

    return {"status": "ok", "data": response}


def end_session(user_id: str, consume_credit: bool = False):
    user_id = str(user_id)
    session = SESSIONS.get(user_id) or _restore_session_from_state(user_id)
    if session:
        cleanup_session_files(session)
    if user_id in SESSIONS:
        del SESSIONS[user_id]
    clear_state(user_id)

    if consume_credit:
        complete_session(user_id)
    else:
        release_active_session(user_id)

    users.update_one(
        {"user_id": user_id},
        {"$set": {"session_access": 0, "current_session_plan": None, "bot_state": None}},
        upsert=True,
    )

    return {"status": "ended"}
