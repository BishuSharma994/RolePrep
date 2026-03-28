import hashlib
import hmac

import razorpay
from backend.utils.config import RAZORPAY_KEY, RAZORPAY_SECRET, RAZORPAY_WEBHOOK_SECRET

PLAN_PRICING = {
    "session": {
        "amount": 100,
        "description": "RolePrep Digital Interview Service",
    },
    "subscription": {
        "amount": 200,
        "description": "RolePrep Digital Interview Service",
    },
}

RAZORPAY_KEY_ID = RAZORPAY_KEY
RAZORPAY_KEY_SECRET = RAZORPAY_SECRET

if not RAZORPAY_KEY_ID:
    raise ValueError("Missing RAZORPAY_KEY or RAZORPAY_KEY_ID")

if not RAZORPAY_KEY_SECRET:
    raise ValueError("Missing RAZORPAY_SECRET or RAZORPAY_KEY_SECRET")

if not RAZORPAY_KEY_ID.startswith("rzp_test_"):
    raise ValueError("Razorpay test mode key required")

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def create_payment_link(user_id, plan_type):
    if plan_type not in PLAN_PRICING:
        raise ValueError("Unsupported plan_type")

    plan = PLAN_PRICING[plan_type]
    payment_link = client.payment_link.create(
        {
            "amount": plan["amount"],
            "currency": "INR",
            "accept_partial": False,
            "description": plan["description"],
            "notify": {
                "sms": False,
                "email": False,
            },
            "reminder_enable": True,
            "notes": {
                "user_id": user_id,
                "plan_type": plan_type,
            },
        }
    )

    return payment_link["short_url"]


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    if not RAZORPAY_WEBHOOK_SECRET:
        raise ValueError("Missing RAZORPAY_WEBHOOK_SECRET")

    digest = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, signature)
