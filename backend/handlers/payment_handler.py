from backend.payment_store import record_payment
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
def confirm_payment(user_id: str, plan_type: str, payment_id: str):
    print("CONFIRM PAYMENT:", user_id, plan_type, payment_id)

    normalized_plan = "premium" if plan_type == "subscription" else plan_type
    if not record_payment(payment_id, user_id, normalized_plan):
        return {
            "status": "duplicate",
            "payment_id": payment_id,
        }

    # --- SESSION PLAN ---
    if normalized_plan == "session":
        add_session_credits(user_id, 1)

        return {
            "status": "success",
            "type": "session",
            "message": "1 session credit added",
            "payment_id": payment_id,
        }

    # --- PREMIUM PLAN (TIME-BASED) ---
    if normalized_plan == "premium":
        activate_subscription(user_id, days=1)

        return {
            "status": "success",
            "type": "premium",
            "message": "Premium activated",
            "payment_id": payment_id,
        }

    raise ValueError("Invalid plan_type")
