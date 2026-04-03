import time

from pymongo.errors import DuplicateKeyError

from backend.services.db import users


def _default_user(user_id):
    return {
        "user_id": user_id,
        "session_credits": 0,
        "subscription_expiry": 0,
        "daily_usage": 0,
        "last_active_date": 0,
        "selected_plan": "free",
        "session_access": 0,
        "current_session_plan": None,
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
            "last_active_date": int(user.get("last_active_date", 0) or 0),
            "selected_plan": user.get("selected_plan", "free"),
            "session_access": int(user.get("session_access", 0) or 0),
            "current_session_plan": user.get("current_session_plan"),
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
    duration_sec = int(duration_sec or 2419200)
    new_expiry = base_time + duration_sec
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


def resolve_plan(user):
    now = int(time.time())

    if int(user.get("subscription_expiry", 0) or 0) > now:
        return "premium"

    if int(user.get("session_credits", 0) or 0) > 0:
        return "session"

    return "free"


def _current_day(now):
    return now // 86400


def _normalize_daily_usage(user_id, user):
    current_day = _current_day(int(time.time()))
    stored_day = user.get("last_active_date", 0)
    if not isinstance(stored_day, int):
        stored_day = 0

    if stored_day != current_day:
        users.update_one(
            {"user_id": user_id},
            {"$set": {"daily_usage": 0, "last_active_date": current_day}},
            upsert=True,
        )
        user["daily_usage"] = 0
        user["last_active_date"] = current_day

    return user


def can_start_session(user_id):
    user = _normalize_daily_usage(user_id, get_user(user_id))
    plan = resolve_plan(user)

    if plan == "premium":
        return True

    if plan == "session":
        return int(user.get("session_credits", 0) or 0) > 0

    return int(user.get("daily_usage", 0) or 0) < 1


def start_session(user_id):
    user = _normalize_daily_usage(user_id, get_user(user_id))
    plan = resolve_plan(user)

    if plan == "premium":
        users.update_one(
            {"user_id": user_id},
            {"$set": {"session_access": 0, "current_session_plan": "premium"}},
            upsert=True,
        )
        return True

    if plan == "session":
        result = users.update_one(
            {"user_id": user_id, "session_credits": {"$gt": 0}},
            {
                "$inc": {"session_credits": -1},
                "$set": {"session_access": 0, "current_session_plan": "session"},
            },
            upsert=False,
        )
        return result.modified_count == 1

    if int(user.get("daily_usage", 0) or 0) >= 1:
        return False

    current_day = _current_day(int(time.time()))
    result = users.update_one(
        {"user_id": user_id, "daily_usage": {"$lt": 1}},
        {
            "$inc": {"daily_usage": 1},
            "$set": {
                "session_access": 0,
                "current_session_plan": "free",
                "last_active_date": current_day,
            },
        },
        upsert=True,
    )
    return result.modified_count == 1 or result.upserted_id is not None


def can_ask_question(user_id):
    user = get_user(user_id)
    active_plan = user.get("current_session_plan") or resolve_plan(user)

    if active_plan == "premium":
        return True

    if active_plan == "session":
        return True

    session_access = int(user.get("session_access", 0) or 0)
    if session_access >= 5:
        return False

    users.update_one(
        {"user_id": user_id},
        {"$inc": {"session_access": 1}},
        upsert=True,
    )
    return True
