import time
from datetime import datetime

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.services.activity import increment_sessions_completed, increment_sessions_started
from backend.services.db import users

SESSION_TIMEOUT_SECONDS = 1800


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
        "active_session": False,
        "active_session_plan": None,
        "session_started_at": None,
        "last_session_activity_at": None,
        "last_active_at": None,
        "created_at": None,
        "last_payment_at": None,
        "sessions_started": 0,
        "sessions_completed": 0,
        "usage_reserved_for": None,
        "verified_email": None,
        "last_login_at": None,
    }


def get_user(user_id):
    user_id = str(user_id)
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
    stored_user = _default_user(str(user["user_id"]))
    stored_user.update(
        {
            "session_credits": int(user.get("session_credits", 0) or 0),
            "subscription_expiry": int(user.get("subscription_expiry", 0) or 0),
            "daily_usage": int(user.get("daily_usage", 0) or 0),
            "last_active_date": int(user.get("last_active_date", 0) or 0),
            "selected_plan": user.get("selected_plan", "free"),
            "session_access": int(user.get("session_access", 0) or 0),
            "current_session_plan": user.get("current_session_plan"),
            "active_session": bool(user.get("active_session", False)),
            "active_session_plan": user.get("active_session_plan"),
            "session_started_at": user.get("session_started_at"),
            "last_session_activity_at": user.get("last_session_activity_at"),
            "last_active_at": user.get("last_active_at"),
            "created_at": user.get("created_at"),
            "last_payment_at": user.get("last_payment_at"),
            "sessions_started": int(user.get("sessions_started", 0) or 0),
            "sessions_completed": int(user.get("sessions_completed", 0) or 0),
            "usage_reserved_for": user.get("usage_reserved_for"),
            "verified_email": user.get("verified_email"),
            "last_login_at": user.get("last_login_at"),
        }
    )
    users.update_one(
        {"user_id": str(user["user_id"])},
        {"$set": stored_user},
        upsert=True,
    )


def set_user_state(user_id, state: dict):
    user_id = str(user_id)
    payload = dict(state or {})
    if not payload:
        return
    now = datetime.utcnow()
    users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                **payload,
                "last_active_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


def clear_user_state(user_id, fields):
    user_id = str(user_id)
    unset_fields = {field: "" for field in fields}
    if not unset_fields:
        return
    users.update_one(
        {"user_id": user_id},
        {"$unset": unset_fields},
        upsert=True,
    )

def add_credits(user_id, credits):
    now = datetime.utcnow()
    users.update_one(
        {"user_id": str(user_id)},
        {
            "$inc": {"session_credits": int(credits)},
            "$set": {"last_active_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


def activate_premium(user_id, duration_sec=None):
    now = int(time.time())
    user = users.find_one({"user_id": str(user_id)}) or {}
    current_expiry = int(user.get("subscription_expiry", 0) or 0)
    base_time = max(now, current_expiry)
    duration_sec = int(duration_sec or 2419200)
    new_expiry = base_time + duration_sec
    activity_now = datetime.utcnow()
    users.update_one(
        {"user_id": str(user_id)},
        {
            "$set": {
                "subscription_expiry": new_expiry,
                "last_active_at": activity_now,
            },
            "$setOnInsert": {"created_at": activity_now},
        },
        upsert=True,
    )


def get_user_state(user_id):
    user = get_user(user_id)

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
        "active_session": bool(user.get("active_session")),
        "active_session_plan": user.get("active_session_plan"),
        "selected_plan": user.get("selected_plan", "free"),
        "session_started_at": user.get("session_started_at"),
        "last_session_activity_at": user.get("last_session_activity_at"),
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
            {"user_id": str(user_id)},
            {"$set": {"daily_usage": 0, "last_active_date": current_day}},
            upsert=True,
        )
        user["daily_usage"] = 0
        user["last_active_date"] = current_day

    return user


def is_session_timed_out(user_id) -> bool:
    user = get_user(user_id)
    if not user.get("active_session"):
        return False

    last_activity = int(user.get("last_session_activity_at", 0) or 0)
    if not last_activity:
        return False

    return int(time.time()) - last_activity > SESSION_TIMEOUT_SECONDS


def touch_active_session(user_id):
    now = datetime.utcnow()
    users.update_one(
        {"user_id": str(user_id), "active_session": True},
        {
            "$set": {
                "last_session_activity_at": int(time.time()),
                "last_active_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=False,
    )


def release_active_session(user_id):
    now = datetime.utcnow()
    users.update_one(
        {"user_id": str(user_id)},
        {
            "$set": {
                "active_session": False,
                "active_session_plan": None,
                "current_session_plan": None,
                "session_access": 0,
                "last_active_at": now,
            },
            "$unset": {
                "session_started_at": "",
                "last_session_activity_at": "",
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


def activate_session_access(user_id, plan):
    user_id = str(user_id)
    now = int(time.time())
    activity_now = datetime.utcnow()
    active_plan = "premium" if plan == "premium" else "session"
    update = {
        "active_session": True,
        "active_session_plan": active_plan,
        "current_session_plan": active_plan,
        "selected_plan": "premium" if active_plan == "premium" else "session_10",
        "session_access": 0,
        "session_started_at": now,
        "last_session_activity_at": now,
        "last_active_at": activity_now,
    }
    users.update_one(
        {"user_id": user_id},
        {"$set": update, "$setOnInsert": {"created_at": activity_now}},
        upsert=True,
    )


def has_active_session(user_id):
    user = get_user(user_id)
    return bool(user.get("active_session"))


def can_start_session(user_id):
    user = _normalize_daily_usage(user_id, get_user(user_id))

    if user.get("active_session"):
        if is_session_timed_out(user_id):
            return False
        return True

    plan = resolve_plan(user)

    if plan == "premium":
        return True

    if plan == "session":
        return int(user.get("session_credits", 0) or 0) > 0

    return int(user.get("daily_usage", 0) or 0) < 1


def start_session(user_id):
    user_id = str(user_id)
    user = _normalize_daily_usage(user_id, get_user(user_id))
    now = int(time.time())
    activity_now = datetime.utcnow()

    if user.get("active_session"):
        if is_session_timed_out(user_id):
            return False
        touch_active_session(user_id)
        return True

    plan = resolve_plan(user)

    if plan == "premium":
        result = users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "active_session": True,
                    "active_session_plan": "premium",
                    "current_session_plan": "premium",
                    "session_access": 0,
                    "session_started_at": now,
                    "last_session_activity_at": now,
                    "last_active_at": activity_now,
                    "selected_plan": "premium",
                }
            },
            upsert=True,
        )
        if result.acknowledged:
            increment_sessions_started(user_id)
        return result.acknowledged

    if plan == "session":
        result = users.update_one(
            {"user_id": user_id, "session_credits": {"$gt": 0}},
            {
                "$set": {
                    "active_session": True,
                    "active_session_plan": "session",
                    "current_session_plan": "session",
                    "session_access": 0,
                    "session_started_at": now,
                    "last_session_activity_at": now,
                    "last_active_at": activity_now,
                }
            },
            upsert=False,
        )
        if result.modified_count == 1:
            increment_sessions_started(user_id)
        return result.modified_count == 1

    if int(user.get("daily_usage", 0) or 0) >= 1:
        return False

    current_day = _current_day(now)
    result = users.update_one(
        {"user_id": user_id, "daily_usage": {"$lt": 1}},
        {
            "$inc": {"daily_usage": 1},
            "$set": {
                "active_session": True,
                "active_session_plan": "free",
                "current_session_plan": "free",
                "session_access": 0,
                "session_started_at": now,
                "last_session_activity_at": now,
                "last_active_at": activity_now,
                "last_active_date": current_day,
            },
        },
        upsert=True,
    )
    if result.modified_count == 1 or result.upserted_id is not None:
        increment_sessions_started(user_id)
    return result.modified_count == 1 or result.upserted_id is not None


def complete_session(user_id):
    user_id = str(user_id)
    user = get_user(user_id)
    active_plan = user.get("active_session_plan") or user.get("current_session_plan")
    activity_now = datetime.utcnow()

    if active_plan == "session" and user.get("active_session"):
        result = users.find_one_and_update(
            {"user_id": user_id, "active_session": True},
            {
                "$inc": {"session_credits": -1},
                "$set": {
                    "active_session": False,
                    "active_session_plan": None,
                    "current_session_plan": None,
                    "session_access": 0,
                    "last_active_at": activity_now,
                },
                "$unset": {
                    "session_started_at": "",
                    "last_session_activity_at": "",
                },
            },
            return_document=ReturnDocument.AFTER,
        )
        if result is not None:
            increment_sessions_completed(user_id)
        return result is not None

    release_active_session(user_id)
    increment_sessions_completed(user_id)
    return True


def can_ask_question(user_id):
    user = get_user(user_id)
    active_plan = user.get("current_session_plan") or user.get("active_session_plan") or resolve_plan(user)

    if active_plan in {"premium", "session"}:
        touch_active_session(user_id)
        return True

    session_access = int(user.get("session_access", 0) or 0)
    if session_access >= 5:
        return False

    result = users.update_one(
        {"user_id": str(user_id)},
        {
            "$inc": {"session_access": 1},
            "$set": {"last_session_activity_at": int(time.time())},
        },
        upsert=True,
    )
    return result.acknowledged
