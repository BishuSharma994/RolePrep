from datetime import datetime

from pymongo import ReturnDocument

from backend.services.db import users
from backend.user_store import activate_premium, add_credits, get_user, update_user


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def get_user_plan(user_id: str) -> str:
    if is_subscription_active(user_id):
        return "premium"
    if get_session_credits(user_id) > 0:
        return "session"
    return "free"


def set_user_plan(user_id: str, plan: str):
    users.update_one(
        {"user_id": user_id},
        {"$set": {"selected_plan": plan}},
        upsert=True,
    )


def increment_usage(user_id: str):
    today = _today()
    users.update_one(
        {
            "user_id": user_id,
            "session_access": "free",
            "usage_reserved_for": today,
        },
        {
            "$inc": {"daily_usage": 1},
            "$set": {"last_active_date": today},
            "$unset": {"usage_reserved_for": ""},
        },
        upsert=False,
    )


def get_usage(user_id: str) -> int:
    user = get_user(user_id)
    today = _today()
    if user.get("last_active_date") != today:
        return 0

    return int(user.get("daily_usage", 0) or 0)


def add_session_credits(user_id: str, credits: int):
    add_credits(user_id, credits)


def get_session_credits(user_id: str) -> int:
    user = get_user(user_id)
    return int(user.get("session_credits", 0) or 0)


def use_session_credit(user_id: str) -> bool:
    result = users.find_one_and_update(
        {"user_id": user_id, "session_credits": {"$gt": 0}},
        {
            "$inc": {"session_credits": -1},
            "$set": {"session_access": "credit"},
            "$unset": {"usage_reserved_for": ""},
        },
        return_document=ReturnDocument.AFTER,
    )
    if result is not None:
        return True

    get_user(user_id)
    return False


def activate_subscription(user_id: str, days: int):
    activate_premium(user_id, days * 86400)


def is_subscription_active(user_id: str) -> bool:
    now = int(datetime.utcnow().timestamp())
    user = get_user(user_id)
    return int(user.get("subscription_expiry", 0) or 0) > now


def can_start_session(user_id: str) -> bool:
    if is_subscription_active(user_id):
        users.update_one(
            {"user_id": user_id},
            {
                "$set": {"session_access": "premium"},
                "$unset": {"usage_reserved_for": ""},
            },
            upsert=True,
        )
        return True

    if use_session_credit(user_id):
        return True

    today = _today()
    result = users.find_one_and_update(
        {
            "user_id": user_id,
            "$or": [
                {"last_active_date": {"$ne": today}},
                {
                    "last_active_date": today,
                    "daily_usage": {"$lt": 1},
                    "usage_reserved_for": {"$ne": today},
                },
            ],
        },
        {
            "$set": {
                "last_active_date": today,
                "daily_usage": 0,
                "session_access": "free",
                "usage_reserved_for": today,
            }
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return result is not None


def get_current_access_mode(user_id: str) -> str:
    if is_subscription_active(user_id):
        return "premium"

    user = get_user(user_id)
    return user.get("session_access") or "free"


def clear_session_access(user_id: str):
    users.update_one(
        {"user_id": user_id},
        {"$unset": {"session_access": "", "usage_reserved_for": ""}},
        upsert=False,
    )


def can_ask_question(user_id: str, current_q_count: int) -> bool:
    if get_current_access_mode(user_id) == "free":
        return current_q_count < 5
    return True
