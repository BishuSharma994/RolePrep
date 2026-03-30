import json

from fastapi import APIRouter, Header, HTTPException, Request

from backend.payment_store import confirm_payment
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
async def payment_webhook(
    request: Request,
    x_razorpay_signature: str = Header(...),
):
    raw_body = await request.body()

    # --- SIGNATURE VERIFICATION ---
    if not verify_webhook_signature(raw_body, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="invalid_signature")

    # --- PARSE PAYLOAD ---
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_payload") from exc

    event = payload.get("event")
    event_id = extract_event_id(payload)
    if not event_id:
        raise HTTPException(status_code=400, detail="missing_event_id")

    log_event("webhook_received", {"event_id": event_id, "event": event})

    if is_event_processed(event_id):
        log_event("webhook_duplicate", {"event_id": event_id, "event": event})
        return {"status": "duplicate"}

    # =========================
    # ONE-TIME PAYMENT FLOW
    # =========================
    if event == "payment.captured":
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment.get("id")

        notes = payment.get("notes", {})
        user_id = notes.get("user_id")
        plan = notes.get("plan")

        if not user_id or not plan or not payment_id:
            raise HTTPException(status_code=400, detail="missing_payment_notes")

        try:
            success = confirm_payment(payment_id, user_id, plan)
            if success:
                if not mark_event_processed(event_id):
                    log_event("webhook_duplicate", {"event_id": event_id, "event": event})
                    return {"status": "duplicate"}
                log_event(
                    "webhook_processed",
                    {
                        "event_id": event_id,
                        "payment_id": payment_id,
                        "user_id": user_id,
                        "plan": plan,
                    },
                )
                return {"status": "processed"}

            log_event(
                "payment_duplicate",
                {
                    "event_id": event_id,
                    "payment_id": payment_id,
                    "user_id": user_id,
                    "plan": plan,
                },
            )
            return {"status": "duplicate"}
        except Exception:
            log_event(
                "webhook_failed",
                {
                    "event_id": event_id,
                    "payment_id": payment_id,
                    "user_id": user_id,
                    "plan": plan,
                },
            )
            raise

    # =========================
    # SUBSCRIPTION FLOW
    # =========================
    elif event.startswith("subscription."):
        subscription = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        payment_id = subscription.get("id") or event_id

        notes = subscription.get("notes", {})
        user_id = notes.get("user_id")
        plan = notes.get("plan")

        if not user_id or not plan:
            raise HTTPException(status_code=400, detail="missing_subscription_notes")

        try:
            success = confirm_payment(payment_id, user_id, plan)
            if success:
                if not mark_event_processed(event_id):
                    log_event("webhook_duplicate", {"event_id": event_id, "event": event})
                    return {"status": "duplicate"}
                log_event(
                    "webhook_processed",
                    {
                        "event_id": event_id,
                        "payment_id": payment_id,
                        "user_id": user_id,
                        "plan": plan,
                    },
                )
                return {"status": "processed"}

            log_event(
                "payment_duplicate",
                {
                    "event_id": event_id,
                    "payment_id": payment_id,
                    "user_id": user_id,
                    "plan": plan,
                },
            )
            return {"status": "duplicate"}
        except Exception:
            log_event(
                "webhook_failed",
                {
                    "event_id": event_id,
                    "payment_id": payment_id,
                    "user_id": user_id,
                    "plan": plan,
                },
            )
            raise

    # =========================
    # IGNORE EVERYTHING ELSE
    # =========================
    log_event("webhook_ignored", {"event_id": event_id, "event": event})
    return {"status": "ignored"}
