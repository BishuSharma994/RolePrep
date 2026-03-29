import json

from fastapi import APIRouter, Header, HTTPException, Request

from backend.handlers.payment_handler import confirm_payment
from backend.services.payment import verify_webhook_signature
from backend.webhook_store import is_event_processed, mark_event_processed

router = APIRouter()


def extract_event_id(payload: dict) -> str | None:
    if payload.get("id"):
        return str(payload["id"])

    payment_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("id")
    if payment_id:
        return f"{payload.get('event')}:{payment_id}"

    subscription_id = payload.get("payload", {}).get("subscription", {}).get("entity", {}).get("id")
    if subscription_id:
        return f"{payload.get('event')}:{subscription_id}"

    created_at = payload.get("created_at")
    event = payload.get("event")
    if event and created_at is not None:
        return f"{event}:{created_at}"

    return None


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

    if is_event_processed(event_id):
        return {"status": "duplicate"}

    if not mark_event_processed(event_id):
        return {"status": "duplicate"}

    print("EVENT:", event)

    # =========================
    # ONE-TIME PAYMENT FLOW
    # =========================
    if event == "payment.captured":
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = payment.get("id")

        notes = payment.get("notes", {})
        user_id = notes.get("user_id")
        plan_type = notes.get("plan")

        print("USER_ID:", user_id)
        print("PLAN:", plan_type)

        if not user_id or not plan_type or not payment_id:
            raise HTTPException(status_code=400, detail="missing_payment_notes")

        return confirm_payment(user_id, plan_type, payment_id)

    # =========================
    # SUBSCRIPTION FLOW
    # =========================
    elif event.startswith("subscription."):
        subscription = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        payment_id = subscription.get("id") or event_id

        notes = subscription.get("notes", {})
        user_id = notes.get("user_id")
        plan_type = notes.get("plan") or "premium"

        print("SUB USER_ID:", user_id)
        print("SUB PLAN:", plan_type)

        if not user_id:
            raise HTTPException(status_code=400, detail="missing_subscription_notes")

        return confirm_payment(user_id, plan_type, payment_id)

    # =========================
    # IGNORE EVERYTHING ELSE
    # =========================
    return {"status": "ignored"}
