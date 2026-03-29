from datetime import datetime
import json

from fastapi import APIRouter, Header, HTTPException, Request

from backend.handlers.payment_handler import confirm_payment
from backend.services.db import events
from backend.services.payment import verify_webhook_signature

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

    existing_event = events.find_one({"event_id": event_id}, {"_id": 1})
    if existing_event:
        return {"status": "duplicate"}

    events.insert_one(
        {
            "event_id": event_id,
            "event": event,
            "created_at": datetime.utcnow(),
        }
    )

    print("EVENT:", event)

    # =========================
    # ONE-TIME PAYMENT FLOW
    # =========================
    if event == "payment.captured":
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})

        notes = payment.get("notes", {})
        user_id = notes.get("user_id")
        plan_type = notes.get("plan")

        print("USER_ID:", user_id)
        print("PLAN:", plan_type)

        if not user_id or not plan_type:
            raise HTTPException(status_code=400, detail="missing_payment_notes")

        return confirm_payment(user_id, plan_type)

    # =========================
    # SUBSCRIPTION FLOW
    # =========================
    elif event.startswith("subscription."):
        subscription = payload.get("payload", {}).get("subscription", {}).get("entity", {})

        notes = subscription.get("notes", {})
        user_id = notes.get("user_id")
        plan_type = notes.get("plan")

        print("SUB USER_ID:", user_id)
        print("SUB PLAN:", plan_type)

        if not user_id:
            raise HTTPException(status_code=400, detail="missing_subscription_notes")

        # reuse same handler or create separate one
        return confirm_payment(user_id, plan_type or "subscription")

    # =========================
    # IGNORE EVERYTHING ELSE
    # =========================
    return {"status": "ignored"}
