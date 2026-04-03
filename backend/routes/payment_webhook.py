import json

from fastapi import APIRouter, Request

from backend.bot.telegram_bot import app
from backend.payment_store import is_payment_processed, process_captured_payment
from backend.services.activity import update_last_payment_at, update_user_last_active
from backend.services.interview_flow import DISCLAIMER_TEXT, activate_paid_session, get_interview_entry
from backend.services.payment import verify_webhook_signature
from backend.utils.logger import log_event
from backend.webhook_store import is_event_processed, mark_event_processed

router = APIRouter()


def extract_event_id(payload: dict) -> str | None:
    event_id = payload.get("id")
    if event_id is None:
        return None
    return str(event_id)


async def auto_start_paid_session(user_id: str, plan: str):
    update_user_last_active(user_id)
    activate_paid_session(user_id, plan)
    entry = get_interview_entry(user_id)
    await app.bot.send_message(chat_id=int(user_id), text="Payment received. Your interview is starting now.")
    await app.bot.send_message(chat_id=int(user_id), text=DISCLAIMER_TEXT)
    await app.bot.send_message(chat_id=int(user_id), text=entry["text"])


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

    update_user_last_active(user_id)

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
        update_last_payment_at(user_id)
        if event_id:
            mark_event_processed(event_id)
        try:
            await auto_start_paid_session(str(user_id), str(plan))
        except Exception as exc:
            log_event(
                "webhook_auto_start_failed",
                {
                    "event_id": event_id,
                    "payment_id": payment_id,
                    "user_id": str(user_id),
                    "plan": plan,
                    "error": repr(exc),
                },
            )
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
