import json

from fastapi import APIRouter, Request

from backend.payment_store import is_payment_processed, process_captured_payment
from backend.services.payment import verify_webhook_signature
from backend.utils.logger import log_event
from backend.webhook_store import is_event_processed, mark_event_processed

router = APIRouter()


def extract_event_id(payload: dict) -> str | None:
    event_id = payload.get("id")
    if event_id is None:
        return None
    return str(event_id)


@router.post("/webhook/razorpay")
async def payment_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature")

    try:
        if not signature or not verify_webhook_signature(raw_body, signature):
            log_event(
                "webhook_signature_failed",
                {
                    "signature_present": bool(signature),
                },
            )
            return {"status": "invalid"}
    except Exception as exc:
        log_event(
            "webhook_signature_failed",
            {
                "signature_present": bool(signature),
                "error": repr(exc),
            },
        )
        return {"status": "invalid"}

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        log_event("webhook_payload_invalid", {"error": repr(exc)})
        return {"status": "error"}

    event = payload.get("event")
    if event != "payment.captured":
        log_event("webhook_ignored", {"event": event})
        return {"status": "ignored"}

    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    payment_id = payment.get("id")
    status = payment.get("status")
    notes = payment.get("notes", {}) or {}
    user_id = notes.get("user_id")
    plan = notes.get("plan")
    event_id = extract_event_id(payload) or str(payment_id or "")

    log_event(
        "webhook_received",
        {
            "event_id": event_id,
            "event": event,
            "payment_id": payment_id,
            "payment_status": status,
            "user_id": str(user_id) if user_id is not None else None,
            "plan": plan,
        },
    )

    if not payment_id or status != "captured" or not user_id or not plan:
        log_event(
            "webhook_validation_failed",
            {
                "event_id": event_id,
                "payment_id": payment_id,
                "payment_status": status,
                "user_id": str(user_id) if user_id is not None else None,
                "plan": plan,
            },
        )
        return {"status": "error"}

    event_already_processed = bool(event_id) and is_event_processed(event_id)
    payment_already_processed = is_payment_processed(payment_id)

    if event_already_processed and payment_already_processed:
        log_event(
            "webhook_duplicate",
            {
                "event_id": event_id,
                "payment_id": payment_id,
                "user_id": str(user_id),
                "plan": plan,
                "reason": "event_and_payment_already_processed",
            },
        )
        return {"status": "duplicate"}

    if event_already_processed and not payment_already_processed:
        log_event(
            "webhook_recovery_attempt",
            {
                "event_id": event_id,
                "payment_id": payment_id,
                "user_id": str(user_id),
                "plan": plan,
            },
        )

    try:
        processing_status = process_captured_payment(payment_id, user_id, plan, event_id)
    except Exception as exc:
        log_event(
            "webhook_processing_failed",
            {
                "event_id": event_id,
                "payment_id": payment_id,
                "user_id": str(user_id),
                "plan": plan,
                "error": repr(exc),
            },
        )
        return {"status": "error"}

    if processing_status == "processed":
        if event_id:
            mark_event_processed(event_id)
        log_event(
            "webhook_processed",
            {
                "event_id": event_id,
                "payment_id": payment_id,
                "user_id": str(user_id),
                "plan": plan,
            },
        )
        return {"status": "success"}

    if processing_status in {"duplicate", "in_progress"}:
        log_event(
            "webhook_duplicate",
            {
                "event_id": event_id,
                "payment_id": payment_id,
                "user_id": str(user_id),
                "plan": plan,
                "reason": processing_status,
            },
        )
        return {"status": "duplicate"}

    log_event(
        "webhook_processing_failed",
        {
            "event_id": event_id,
            "payment_id": payment_id,
            "user_id": str(user_id),
            "plan": plan,
            "error": f"unexpected_processing_status:{processing_status}",
        },
    )
    return {"status": "error"}
