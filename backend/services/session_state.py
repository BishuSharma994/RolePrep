import time

from backend.services.db import users


SESSION_STATE_FIELDS = (
    "current_question",
    "current_stage",
    "session_id",
    "last_answer",
    "last_question_ts",
    "updated_at",
    "session_role",
    "session_jd_text",
    "session_history",
    "session_scores",
    "session_question_count",
    "session_parser_data",
    "session_resume_path",
    "session_jd_path",
    "session_pending_answer",
    "anti_cheat_flags",
    "pending_followup",
    "latest_answer_analysis",
)


def save_state(user_id: str, state: dict):
    payload = dict(state or {})
    payload["updated_at"] = payload.get("updated_at", time.time())
    users.update_one(
        {"user_id": user_id},
        {"$set": payload},
        upsert=True,
    )


def load_state(user_id: str) -> dict:
    projection = {field: 1 for field in SESSION_STATE_FIELDS}
    projection["_id"] = 0
    stored_state = users.find_one({"user_id": user_id}, projection) or {}
    return {key: value for key, value in stored_state.items() if value is not None}


def clear_state(user_id: str):
    users.update_one(
        {"user_id": user_id},
        {"$unset": {field: "" for field in SESSION_STATE_FIELDS}},
        upsert=True,
    )
