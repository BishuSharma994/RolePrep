import os

import razorpay
from dotenv import dotenv_values

PLAN_PRICING = {
    "session": {
        "amount": 9900,
        "description": "RolePrep session purchase",
    },
    "subscription": {
        "amount": 49900,
        "description": "RolePrep 30-day subscription",
    },
}

_ENV = dotenv_values(".env")


def _get_env_value(key: str):
    value = os.getenv(key) or _ENV.get(key)
    if isinstance(value, str):
        return value.strip()
    return value


RAZORPAY_KEY_ID = _get_env_value("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = _get_env_value("RAZORPAY_KEY_SECRET")

if not RAZORPAY_KEY_ID:
    raise ValueError("Missing RAZORPAY_KEY_ID")

if not RAZORPAY_KEY_SECRET:
    raise ValueError("Missing RAZORPAY_KEY_SECRET")

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


def create_payment_link(user_id, plan_type):
    if plan_type not in PLAN_PRICING:
        raise ValueError("Unsupported plan_type")

    plan = PLAN_PRICING[plan_type]
    payment_link = client.payment_link.create(
        {
            "amount": plan["amount"],
            "currency": "INR",
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
