import time

from pymongo.errors import DuplicateKeyError

from backend.services.db import webhooks


def is_event_processed(event_id):
    return webhooks.find_one({"event_id": event_id}) is not None


def mark_event_processed(event_id):
    try:
        webhooks.insert_one(
            {
                "event_id": str(event_id),
                "created_at": int(time.time()),
            }
        )
        return True
    except DuplicateKeyError:
        return False
