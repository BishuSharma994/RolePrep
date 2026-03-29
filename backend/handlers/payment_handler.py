from datetime import datetime, timedelta

from backend.services.payment import create_payment_link
from backend.services.plan_manager import (
    add_session_credits,
    activate_subscription,
)

# ===== CONSTANT =====
POLICY_URL = "https://your-policy-url.com"  # keep your original URL here


# =========================
# PAYMENT REQUEST (called from bot)
# =========================
def handle_payment_request(user_id: str, plan_type: str):
    payment_link = create_payment_link(user_id, plan_type)

    return {
        "status": "pending",
        "payment_link": payment_link,
    }


# =========================
# PAYMENT CONFIRMATION (called from webhook)
# =========================
def confirm_payment(user_id: str, plan_type: str):
    print("CONFIRM PAYMENT:", user_id, plan_type)

    # --- SESSION PLAN ---
    if plan_type == "session":
        add_session_credits(user_id, 1)

        return {
            "status": "success",
            "type": "session",
            "message": "1 session credit added",
        }

    # --- PREMIUM PLAN (TIME-BASED) ---
    if plan_type == "premium":
        # 1 day example (adjust if needed)
        activate_subscription(user_id, days=1)

        return {
            "status": "success",
            "type": "premium",
            "message": "Premium activated",
        }

    raise ValueError("Invalid plan_type")