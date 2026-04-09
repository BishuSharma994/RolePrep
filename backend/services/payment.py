import hashlib
import hmac
from urllib.parse import urlencode

import razorpay
from backend.utils.config import (
    FRONTEND_APP_URL,
    RAZORPAY_KEY,
    RAZORPAY_SECRET,
    RAZORPAY_WEBHOOK_SECRET,
)

PLAN_PRICING = {
    "session_10": {
        "amount": 1000,
        "description": "RolePrep Digital Interview Service",
    },
    "session_29": {
        "amount": 2900,
        "description": "RolePrep Digital Interview Service",
    },
    "premium": {
        "amount": 9900,
        "description": "RolePrep Digital Interview Service",
    },
}

SUPPORTED_KEY_PREFIXES = ("rzp_test_", "rzp_live_")

RAZORPAY_KEY_ID = RAZORPAY_KEY
RAZORPAY_KEY_SECRET = RAZORPAY_SECRET
_client = None


def _validate_key_id(key_id: str) -> None:
    if not key_id:
        raise ValueError("Missing RAZORPAY_KEY or RAZORPAY_KEY_ID")
    if not key_id.startswith(SUPPORTED_KEY_PREFIXES):
        raise ValueError(
            "Invalid Razorpay key format. Expected a key starting with "
            "'rzp_test_' or 'rzp_live_'."
        )


def get_client():
    global _client

    if _client is not None:
        return _client

    if not RAZORPAY_KEY_SECRET:
        raise ValueError("Missing RAZORPAY_SECRET or RAZORPAY_KEY_SECRET")

    _validate_key_id(RAZORPAY_KEY_ID)
    _client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    return _client


def _payment_callback_url(user_id, plan_type):
    base_url = str(FRONTEND_APP_URL or "https://www.roleprep.in").strip().rstrip("/")
    query = urlencode(
        {
            "payment": "processing",
            "user_id": str(user_id),
            "plan_type": str(plan_type),
        }
    )
    return f"{base_url}/?{query}"


def create_payment_link(user_id, plan_type):
    if plan_type not in PLAN_PRICING:
        raise ValueError("Unsupported plan_type")

    plan = PLAN_PRICING[plan_type]
    client = get_client()

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
                "user_id": str(user_id),
                "plan": plan_type,
            },
            "callback_url": _payment_callback_url(user_id, plan_type),
            "callback_method": "get",
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
