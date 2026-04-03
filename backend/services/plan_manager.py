import time
from datetime import datetime

from backend.services.db import users
from backend.user_store import (
    activate_premium,
    add_credits,
    get_user,
    release_active_session,
    set_user_state,
)


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def get_user_plan(user_id: str) -> str:
    user = get_user(user_id)
    if user.get("active_session"):
        return user.get("active_session_plan") or user.get("current_session_plan") or "session"
    if is_subscription_active(user_id):
        return "premium"
    if get_session_credits(user_id) > 0:
        return "session"
    return "free"


def set_user_plan(user_id: str, plan: str):
    users.update_one(
        {"user_id": str(user_id)},
        {"$set": {"selected_plan": plan}},
        upsert=True,
    )


def increment_usage(user_id: str):
    today = _today()
    users.update_one(
        {
            "user_id": str(user_id),
            "current_session_plan": "free",
        },
        {
            "$inc": {"daily_usage": 1},
            "$set": {"last_active_date": today},
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
    user = get_user(user_id)
    if user.get("active_session") and (user.get("active_session_plan") or user.get("current_session_plan")) == "session":
        return True

    if int(user.get("session_credits", 0) or 0) <= 0:
        return False

    now = int(time.time())
    result = users.update_one(
        {"user_id": str(user_id), "session_credits": {"$gt": 0}},
        {
            "$set": {
                "active_session": True,
                "active_session_plan": "session",
                "current_session_plan": "session",
                "session_access": 0,
                "session_started_at": now,
                "last_session_activity_at": now,
            }
        },
        upsert=False,
    )
    return result.modified_count == 1


def activate_subscription(user_id: str, days: int):
    activate_premium(user_id, days * 86400)


def is_subscription_active(user_id: str) -> bool:
    now = int(datetime.utcnow().timestamp())
    user = get_user(user_id)
    return int(user.get("subscription_expiry", 0) or 0) > now


def can_start_session(user_id: str) -> bool:
    user = get_user(user_id)
    if user.get("active_session"):
        return True

    if is_subscription_active(user_id):
        now = int(time.time())
        set_user_state(
            user_id,
            {
                "active_session": True,
                "active_session_plan": "premium",
                "current_session_plan": "premium",
                "session_started_at": now,
                "last_session_activity_at": now,
                "session_access": 0,
            },
        )
        return True

    if use_session_credit(user_id):
        return True

    today = _today()
    user = get_user(user_id)
    if user.get("last_active_date") != today:
        users.update_one(
            {"user_id": str(user_id)},
            {"$set": {"daily_usage": 0, "last_active_date": today}},
            upsert=True,
        )
        user["daily_usage"] = 0

    if int(user.get("daily_usage", 0) or 0) >= 1:
        return False

    now = int(time.time())
    result = users.update_one(
        {"user_id": str(user_id), "daily_usage": {"$lt": 1}},
        {
            "$inc": {"daily_usage": 1},
            "$set": {
                "last_active_date": today,
                "active_session": True,
                "active_session_plan": "free",
                "current_session_plan": "free",
                "session_started_at": now,
                "last_session_activity_at": now,
                "session_access": 0,
            },
        },
        upsert=True,
    )
    return result.modified_count == 1 or result.upserted_id is not None


def get_current_access_mode(user_id: str) -> str:
    user = get_user(user_id)
    if user.get("active_session"):
        return user.get("active_session_plan") or user.get("current_session_plan") or "free"

    if is_subscription_active(user_id):
        return "premium"

    return user.get("current_session_plan") or "free"


def clear_session_access(user_id: str):
    release_active_session(user_id)


def can_ask_question(user_id: str, current_q_count: int) -> bool:
    if get_current_access_mode(user_id) == "free":
        return current_q_count < 5
    return True
