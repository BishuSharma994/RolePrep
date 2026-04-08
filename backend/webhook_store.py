import time

from pymongo.errors import DuplicateKeyError

from backend.services.db import webhooks


def is_event_processed(event_id):
    return webhooks.find_one({"event_id": event_id}) is not None


def record_webhook_event(event_id, event_type, payload):
    now = int(time.time())
    document = {
        "event_id": str(event_id),
        "event_type": str(event_type or ""),
        "payload": payload,
        "source_created_at": payload.get("created_at") if isinstance(payload, dict) else None,
        "received_at": now,
        "updated_at": now,
        "status": "received",
    }
    try:
        webhooks.insert_one(document)
        return "recorded"
    except DuplicateKeyError:
        existing = webhooks.find_one({"event_id": str(event_id)}, {"status": 1}) or {}
        if existing.get("status") == "processed":
            return "duplicate"
        webhooks.update_one(
            {"event_id": str(event_id)},
            {
                "$set": {
                    "event_type": str(event_type or ""),
                    "payload": payload,
                    "source_created_at": payload.get("created_at") if isinstance(payload, dict) else None,
                    "received_at": now,
                    "updated_at": now,
                    "status": "received",
                }
            },
            upsert=False,
        )
        return "retry"


def update_webhook_event(event_id, status, **fields):
    update_fields = {
        "status": str(status),
        "updated_at": int(time.time()),
    }
    update_fields.update(fields)
    webhooks.update_one(
        {"event_id": str(event_id)},
        {"$set": update_fields},
        upsert=False,
    )


def mark_event_processed(event_id, **fields):
    try:
        result = webhooks.update_one(
            {"event_id": str(event_id)},
            {
                "$set": {
                    "status": "processed",
                    "processed_at": int(time.time()),
                    "updated_at": int(time.time()),
                    **fields,
                },
                "$setOnInsert": {
                    "created_at": int(time.time()),
                },
            },
            upsert=True,
        )
        return bool(result.acknowledged)
    except DuplicateKeyError:
        return False
