from datetime import datetime

from pymongo.errors import DuplicateKeyError

from backend.db import payments


def is_payment_processed(payment_id):
    return payments.find_one({"payment_id": payment_id}, {"_id": 1}) is not None


def record_payment(payment_id, user_id, plan):
    try:
        payments.insert_one(
            {
                "payment_id": str(payment_id),
                "user_id": str(user_id),
                "plan": plan,
                "created_at": datetime.utcnow(),
            }
        )
        return True
    except DuplicateKeyError:
        return False
