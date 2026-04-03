import time
import uuid

from pymongo.errors import DuplicateKeyError

from backend.services.activity import update_last_payment_at
from backend.services.db import audit_logs, payments, users
from backend.user_store import activate_premium, get_user
from backend.utils.logger import log_event

DEFAULT_PREMIUM_DURATION_DAYS = 28
STALE_PROCESSING_SECONDS = 300

PLAN_ALIASES = {
    "session_5": "session_29",
    "unlimited_28": "premium",
}

PLAN_ACTIONS = {
    "session_10": {"type": "sessions", "count": 1},
    "session_29": {"type": "sessions", "count": 5},
    "premium": {"type": "premium", "days": DEFAULT_PREMIUM_DURATION_DAYS},
}


def normalize_plan(plan: str) -> str:
    raw_plan = str(plan or "").strip()
    normalized_plan = PLAN_ALIASES.get(raw_plan, raw_plan)
    if normalized_plan not in PLAN_ACTIONS:
        raise ValueError(f"Unknown plan: {raw_plan}")
    return normalized_plan


def is_payment_processed(payment_id):
    payment = payments.find_one({"payment_id": str(payment_id)}, {"status": 1})
    return payment is not None and payment.get("status") == "processed"


def add_sessions(user_id, count):
    user_id = str(user_id)
    count = int(count)
    get_user(user_id)

    result = users.update_one(
        {"user_id": user_id},
        {"$inc": {"session_credits": count}},
        upsert=True,
    )
    if not result.acknowledged:
        raise RuntimeError(f"Failed to add {count} sessions for user {user_id}")

    user = users.find_one({"user_id": user_id}, {"session_credits": 1, "_id": 0}) or {}
    new_balance = int(user.get("session_credits", 0) or 0)

    log_event(
        "sessions_added",
        {
            "user_id": user_id,
            "sessions_added": count,
            "session_credits": new_balance,
        },
    )
    return new_balance


def set_unlimited(user_id, days=DEFAULT_PREMIUM_DURATION_DAYS):
    user_id = str(user_id)
    days = int(days)
    get_user(user_id)
    activate_premium(user_id, days * 86400)

    user = users.find_one({"user_id": user_id}, {"subscription_expiry": 1, "_id": 0}) or {}
    new_expiry = int(user.get("subscription_expiry", 0) or 0)

    log_event(
        "premium_activated",
        {
            "user_id": user_id,
            "days_added": days,
            "subscription_expiry": new_expiry,
        },
    )
    return new_expiry


def mark_payment_processed(payment_id, processing_token, user_id, plan, event_id=None):
    payment_id = str(payment_id)
    user_id = str(user_id)
    normalized_plan = normalize_plan(plan)
    now = int(time.time())
    update_last_payment_at(user_id)

    result = payments.update_one(
        {"payment_id": payment_id, "processing_token": processing_token},
        {
            "$set": {
                "status": "processed",
                "plan": normalized_plan,
                "raw_plan": str(plan),
                "user_id": user_id,
                "event_id": str(event_id) if event_id else None,
                "processed_at": now,
                "updated_at": now,
            },
            "$unset": {
                "processing_token": "",
                "last_error": "",
            },
        },
        upsert=False,
    )
    if not result.acknowledged or result.matched_count != 1:
        raise RuntimeError(f"Failed to mark payment {payment_id} as processed")

    audit_result = audit_logs.insert_one(
        {
            "type": "payment_processed",
            "user_id": user_id,
            "payment_id": payment_id,
            "plan": normalized_plan,
            "raw_plan": str(plan),
            "event_id": str(event_id) if event_id else None,
            "timestamp": now,
        }
    )
    if not audit_result.acknowledged:
        raise RuntimeError(f"Failed to write audit log for payment {payment_id}")

    log_event(
        "payment_processed",
        {
            "payment_id": payment_id,
            "user_id": user_id,
            "plan": normalized_plan,
            "raw_plan": str(plan),
            "event_id": str(event_id) if event_id else None,
        },
    )
    return True


def mark_payment_failed(payment_id, processing_token, error_message, event_id=None):
    payment_id = str(payment_id)
    result = payments.update_one(
        {"payment_id": payment_id, "processing_token": processing_token},
        {
            "$set": {
                "status": "failed",
                "last_error": str(error_message),
                "event_id": str(event_id) if event_id else None,
                "updated_at": int(time.time()),
            },
            "$unset": {"processing_token": ""},
        },
        upsert=False,
    )
    if not result.acknowledged or result.matched_count != 1:
        raise RuntimeError(f"Failed to mark payment {payment_id} as failed")


def _claim_payment(payment_id, user_id, plan, event_id=None):
    payment_id = str(payment_id)
    user_id = str(user_id)
    raw_plan = str(plan)
    normalized_plan = normalize_plan(raw_plan)
    now = int(time.time())
    processing_token = str(uuid.uuid4())

    processing_state = {
        "user_id": user_id,
        "plan": normalized_plan,
        "raw_plan": raw_plan,
        "event_id": str(event_id) if event_id else None,
        "status": "processing",
        "processing_token": processing_token,
        "last_attempt_at": now,
        "updated_at": now,
    }

    try:
        payments.insert_one(
            {
                "payment_id": payment_id,
                **processing_state,
                "created_at": now,
            }
        )
        return {"status": "claimed", "processing_token": processing_token, "plan": normalized_plan}
    except DuplicateKeyError:
        existing = payments.find_one({"payment_id": payment_id}) or {}
        existing_status = existing.get("status")

        if existing_status == "processed":
            return {"status": "duplicate", "plan": existing.get("plan") or normalized_plan}

        if existing_status == "processing":
            last_attempt_at = int(existing.get("last_attempt_at", 0) or 0)
            if now - last_attempt_at < STALE_PROCESSING_SECONDS:
                return {"status": "in_progress", "plan": existing.get("plan") or normalized_plan}

            claim_filter = {
                "payment_id": payment_id,
                "status": "processing",
                "processing_token": existing.get("processing_token"),
            }
        else:
            claim_filter = {
                "payment_id": payment_id,
                "$or": [
                    {"status": {"$exists": False}},
                    {"status": "failed"},
                ],
            }

        result = payments.update_one(
            claim_filter,
            {
                "$set": processing_state,
                "$unset": {"last_error": ""},
            },
            upsert=False,
        )
        if not result.acknowledged:
            raise RuntimeError(f"Failed to claim payment {payment_id} for processing")

        if result.matched_count != 1:
            refreshed = payments.find_one({"payment_id": payment_id}, {"status": 1, "plan": 1}) or {}
            refreshed_status = refreshed.get("status")
            if refreshed_status == "processed":
                return {"status": "duplicate", "plan": refreshed.get("plan") or normalized_plan}
            if refreshed_status == "processing":
                return {"status": "in_progress", "plan": refreshed.get("plan") or normalized_plan}
            raise RuntimeError(f"Unable to claim payment {payment_id} for processing")

        return {"status": "claimed", "processing_token": processing_token, "plan": normalized_plan}


def process_captured_payment(payment_id, user_id, plan, event_id=None):
    payment_id = str(payment_id)
    user_id = str(user_id)
    raw_plan = str(plan)
    claim = _claim_payment(payment_id, user_id, raw_plan, event_id)

    if claim["status"] != "claimed":
        log_event(
            "payment_skipped",
            {
                "payment_id": payment_id,
                "user_id": user_id,
                "plan": claim.get("plan") or raw_plan,
                "raw_plan": raw_plan,
                "event_id": str(event_id) if event_id else None,
                "reason": claim["status"],
            },
        )
        return claim["status"]

    normalized_plan = claim["plan"]
    processing_token = claim["processing_token"]

    log_event(
        "payment_processing_started",
        {
            "payment_id": payment_id,
            "user_id": user_id,
            "plan": normalized_plan,
            "raw_plan": raw_plan,
            "event_id": str(event_id) if event_id else None,
        },
    )

    try:
        action = PLAN_ACTIONS[normalized_plan]
        if action["type"] == "sessions":
            add_sessions(user_id, action["count"])
        elif action["type"] == "premium":
            set_unlimited(user_id, action["days"])
        else:
            raise ValueError(f"Unsupported plan action for {normalized_plan}")

        mark_payment_processed(payment_id, processing_token, user_id, raw_plan, event_id)
        return "processed"
    except Exception as exc:
        try:
            mark_payment_failed(payment_id, processing_token, repr(exc), event_id)
        except Exception as mark_exc:
            log_event(
                "payment_failure_mark_failed",
                {
                    "payment_id": payment_id,
                    "user_id": user_id,
                    "plan": normalized_plan,
                    "raw_plan": raw_plan,
                    "event_id": str(event_id) if event_id else None,
                    "error": repr(mark_exc),
                    "original_error": repr(exc),
                },
            )
            raise
        log_event(
            "payment_processing_failed",
            {
                "payment_id": payment_id,
                "user_id": user_id,
                "plan": normalized_plan,
                "raw_plan": raw_plan,
                "event_id": str(event_id) if event_id else None,
                "error": repr(exc),
            },
        )
        raise
