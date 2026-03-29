from datetime import datetime, timedelta

from backend.services.db import users


def _ensure_user(user_id: str):
    users.update_one(
        {"user_id": user_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "session_credits": 0,
                "subscription_expires_at": None,
            }
        },
        upsert=True,
    )


def get_user_plan(user_id: str) -> str:
    if is_subscription_active(user_id):
        return "premium"
    if get_session_credits(user_id) > 0:
        return "session"
    return "free"


def set_user_plan(user_id: str, plan: str):
    _ensure_user(user_id)
    users.update_one(
        {"user_id": user_id},
        {"$set": {"selected_plan": plan}},
        upsert=True,
    )


def increment_usage(user_id: str):
    _ensure_user(user_id)


def get_usage(user_id: str) -> int:
    _ensure_user(user_id)
    return 0


def add_session_credits(user_id: str, credits: int):
    _ensure_user(user_id)
    users.update_one(
        {"user_id": user_id},
        {"$inc": {"session_credits": credits}},
        upsert=True,
    )


def get_session_credits(user_id: str) -> int:
    user = users.find_one({"user_id": user_id}, {"session_credits": 1})
    if not user:
        return 0
    return int(user.get("session_credits", 0) or 0)


def use_session_credit(user_id: str) -> bool:
    _ensure_user(user_id)
    result = users.find_one_and_update(
        {"user_id": user_id, "session_credits": {"$gt": 0}},
        {
            "$inc": {"session_credits": -1},
            "$set": {"session_access": "credit"},
        },
    )
    return result is not None


def activate_subscription(user_id: str, days: int):
    _ensure_user(user_id)
    expires_at = datetime.utcnow() + timedelta(days=days)
    users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "subscription_expires_at": expires_at,
                "session_access": "premium",
            }
        },
        upsert=True,
    )


def is_subscription_active(user_id: str) -> bool:
    now = datetime.utcnow()
    user = users.find_one({"user_id": user_id}, {"subscription_expires_at": 1})
    expiry = user.get("subscription_expires_at") if user else None
    return bool(expiry and expiry > now)


def can_start_session(user_id: str) -> bool:
    if is_subscription_active(user_id):
        _ensure_user(user_id)
        users.update_one(
            {"user_id": user_id},
            {"$set": {"session_access": "premium"}},
            upsert=True,
        )
        return True

    return use_session_credit(user_id)


def get_current_access_mode(user_id: str) -> str:
    if is_subscription_active(user_id):
        return "premium"

    user = users.find_one({"user_id": user_id}, {"session_access": 1})
    if not user:
        return "free"
    return user.get("session_access", "free")


def clear_session_access(user_id: str):
    users.update_one(
        {"user_id": user_id},
        {"$unset": {"session_access": ""}},
        upsert=True,
    )


def can_ask_question(user_id: str, current_q_count: int) -> bool:
    if get_current_access_mode(user_id) == "free":
        return current_q_count < 5
    return True
