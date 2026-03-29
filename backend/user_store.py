import time
from backend.db import users_col


def get_user(user_id):
    user = users_col.find_one({"user_id": user_id})

    if not user:
        user = {
            "user_id": user_id,
            "session_credits": 0,
            "subscription_expiry": 0,
            "daily_usage": 0,
            "last_active_date": None
        }
        users_col.insert_one(user)

    return user


def update_user(user):
    users_col.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "session_credits": user["session_credits"],
            "subscription_expiry": user["subscription_expiry"],
            "daily_usage": user["daily_usage"],
            "last_active_date": user["last_active_date"]
        }}
    )


def add_credits(user_id, credits):
    users_col.update_one(
        {"user_id": user_id},
        {"$inc": {"session_credits": credits}}
    )


def activate_premium(user_id, duration_sec):
    expiry = int(time.time()) + duration_sec

    users_col.update_one(
        {"user_id": user_id},
        {"$set": {"subscription_expiry": expiry}}
    )
