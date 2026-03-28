import json

from fastapi import APIRouter, Header, HTTPException, Request

from backend.handlers.payment_handler import confirm_payment
from backend.services.payment import verify_webhook_signature

router = APIRouter()


@router.post("/webhook/razorpay")
async def payment_webhook(
    request: Request,
    x_razorpay_signature: str = Header(...),
):
    raw_body = await request.body()

    if not verify_webhook_signature(raw_body, x_razorpay_signature):
        raise HTTPException(status_code=400, detail="invalid_signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_payload") from exc

    if payload.get("event") != "payment_link.paid":
        return {"status": "ignored"}

    payment_link = payload.get("payload", {}).get("payment_link", {}).get("entity", {})
    notes = payment_link.get("notes", {})
    user_id = notes.get("user_id")
    plan_type = notes.get("plan_type")

    if not user_id or not plan_type:
        raise HTTPException(status_code=400, detail="missing_payment_notes")

    return confirm_payment(user_id, plan_type)
