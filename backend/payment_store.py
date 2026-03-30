import time

from pymongo.errors import DuplicateKeyError

from backend.services.db import audit_logs, payments
from backend.user_store import activate_premium, add_credits
from backend.utils.logger import log_event


def is_payment_processed(payment_id):
    return payments.find_one({"payment_id": payment_id}, {"_id": 1}) is not None


def confirm_payment(payment_id, user_id, plan):
    existing = payments.find_one({"payment_id": str(payment_id)})
    if existing:
        log_event(
            "payment_duplicate",
            {
                "payment_id": str(payment_id),
                "user_id": str(user_id),
                "plan": plan,
            },
        )
        return False

    try:
        payments.insert_one(
            {
                "payment_id": str(payment_id),
                "user_id": str(user_id),
                "plan": plan,
                "created_at": int(time.time()),
            }
        )
    except DuplicateKeyError:
        log_event(
            "payment_duplicate",
            {
                "payment_id": str(payment_id),
                "user_id": str(user_id),
                "plan": plan,
            },
        )
        return False

    if plan == "session_10":
        add_credits(user_id, 1)
    elif plan == "session_29":
        add_credits(user_id, 5)
    elif plan == "premium":
        activate_premium(user_id)

    audit_logs.insert_one(
        {
            "type": "payment_processed",
            "user_id": str(user_id),
            "payment_id": str(payment_id),
            "plan": plan,
            "timestamp": int(time.time()),
        }
    )

    log_event(
        "payment_processed",
        {
            "payment_id": str(payment_id),
            "user_id": str(user_id),
            "plan": plan,
        },
    )
    return True
