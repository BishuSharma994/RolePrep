from datetime import datetime, timedelta

from backend.services.db import users


def update_user_last_active(user_id):
    now = datetime.utcnow()
    users.update_one(
        {"user_id": str(user_id)},
        {
            "$set": {"last_active_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    print("ACTIVE USER UPDATED:", user_id)


def increment_sessions_started(user_id):
    update_user_last_active(user_id)
    users.update_one(
        {"user_id": str(user_id)},
        {
            "$inc": {"sessions_started": 1},
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )


def increment_sessions_completed(user_id):
    update_user_last_active(user_id)
    users.update_one(
        {"user_id": str(user_id)},
        {
            "$inc": {"sessions_completed": 1},
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )


def update_last_payment_at(user_id):
    now = datetime.utcnow()
    users.update_one(
        {"user_id": str(user_id)},
        {
            "$set": {
                "last_payment_at": now,
                "last_active_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    print("ACTIVE USER UPDATED:", user_id)


def get_active_users_24h():
    return users.count_documents(
        {
            "last_active_at": {
                "$gte": datetime.utcnow() - timedelta(hours=24),
            }
        }
    )


def get_active_users_7d():
    return users.count_documents(
        {
            "last_active_at": {
                "$gte": datetime.utcnow() - timedelta(days=7),
            }
        }
    )
