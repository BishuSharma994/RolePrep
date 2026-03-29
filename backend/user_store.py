import time

from backend.db import users


def _default_user(user_id):
    return {
        "user_id": user_id,
        "session_credits": 0,
        "subscription_expiry": 0,
        "daily_usage": 0,
        "last_active_date": None,
        "selected_plan": "free",
        "session_access": None,
        "usage_reserved_for": None,
    }


def get_user(user_id):
    users.update_one(
        {"user_id": user_id},
        {"$setOnInsert": _default_user(user_id)},
        upsert=True,
    )
    user = users.find_one({"user_id": user_id}) or _default_user(user_id)

    patched_fields = {}
    default_user = _default_user(user_id)
    for key, value in default_user.items():
        if key not in user:
            user[key] = value
            patched_fields[key] = value

    if patched_fields:
        users.update_one({"user_id": user_id}, {"$set": patched_fields}, upsert=True)

    return user


def update_user(user):
    stored_user = _default_user(user["user_id"])
    stored_user.update(
        {
            "session_credits": int(user.get("session_credits", 0) or 0),
            "subscription_expiry": int(user.get("subscription_expiry", 0) or 0),
            "daily_usage": int(user.get("daily_usage", 0) or 0),
            "last_active_date": user.get("last_active_date"),
            "selected_plan": user.get("selected_plan", "free"),
            "session_access": user.get("session_access"),
            "usage_reserved_for": user.get("usage_reserved_for"),
        }
    )
    users.update_one(
        {"user_id": user["user_id"]},
        {"$set": stored_user},
        upsert=True,
    )


def add_credits(user_id, credits):
    users.update_one(
        {"user_id": user_id},
        {
            "$setOnInsert": _default_user(user_id),
            "$inc": {"session_credits": int(credits)},
        },
        upsert=True,
    )


def activate_premium(user_id, duration_sec):
    now = int(time.time())
    user = get_user(user_id)
    current_expiry = int(user.get("subscription_expiry", 0) or 0)
    new_expiry = max(now, current_expiry) + int(duration_sec)
    users.update_one(
        {"user_id": user_id},
        {"$set": {"subscription_expiry": new_expiry, "session_access": "premium"}},
        upsert=True,
    )
