import time

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.db import rate_limits
from backend.user_store import get_user, resolve_plan


def check_rate_limit(user_id, limit, window_seconds):
    now = int(time.time())
    window_start = now - window_seconds

    rate_limits.delete_many({"window_start": {"$lt": now - 3600}})

    record = rate_limits.find_one({"user_id": str(user_id)})
    if not record:
        try:
            rate_limits.insert_one(
                {
                    "user_id": str(user_id),
                    "window_start": now,
                    "request_count": 1,
                }
            )
            return True
        except DuplicateKeyError:
            record = rate_limits.find_one({"user_id": str(user_id)})

    reset_record = rate_limits.find_one_and_update(
        {
            "user_id": str(user_id),
            "window_start": {"$lt": window_start},
        },
        {
            "$set": {
                "window_start": now,
                "request_count": 1,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if reset_record is not None:
        return True

    incremented = rate_limits.find_one_and_update(
        {
            "user_id": str(user_id),
            "window_start": {"$gte": window_start},
            "request_count": {"$lt": int(limit)},
        },
        {"$inc": {"request_count": 1}},
        return_document=ReturnDocument.AFTER,
    )
    return incremented is not None


def get_rate_limit_for_user(user_id):
    user = get_user(user_id)
    plan = resolve_plan(user)

    if plan == "premium":
        return 100
    if plan == "session":
        return 30
    return 10


def allow_request(user_id):
    return check_rate_limit(user_id, get_rate_limit_for_user(user_id), 60)
