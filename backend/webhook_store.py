from datetime import datetime

from pymongo.errors import DuplicateKeyError

from backend.db import webhooks


def is_event_processed(event_id):
    return webhooks.find_one({"event_id": event_id}, {"_id": 1}) is not None


def mark_event_processed(event_id):
    try:
        webhooks.insert_one(
            {
                "event_id": str(event_id),
                "created_at": datetime.utcnow(),
            }
        )
        return True
    except DuplicateKeyError:
        return False
