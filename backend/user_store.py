import time

from pymongo.errors import DuplicateKeyError

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
    user = users.find_one({"user_id": user_id})
    if not user:
        user = _default_user(user_id)
        try:
            users.insert_one(user)
        except DuplicateKeyError:
            user = users.find_one({"user_id": user_id}) or user

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
        {"$inc": {"session_credits": int(credits)}},
        upsert=True,
    )


def activate_premium(user_id, duration_sec=None):
    now = int(time.time())
    user = users.find_one({"user_id": user_id}) or {}
    current_expiry = int(user.get("subscription_expiry", 0) or 0)
    base_time = max(now, current_expiry)
    new_expiry = base_time + 2419200
    users.update_one(
        {"user_id": user_id},
        {"$set": {"subscription_expiry": new_expiry}},
        upsert=True,
    )


def get_user_state(user_id):
    user = users.find_one({"user_id": user_id}) or {}

    now = int(time.time())
    credits = int(user.get("session_credits", 0) or 0)
    expiry = int(user.get("subscription_expiry", 0) or 0)
    is_premium = expiry > now
    remaining_seconds = max(0, expiry - now)
    remaining_days = remaining_seconds // 86400

    return {
        "credits": credits,
        "is_premium": is_premium,
        "expiry_ts": expiry,
        "days_left": remaining_days,
    }
