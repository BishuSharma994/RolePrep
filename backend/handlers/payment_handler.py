from backend.services.payment import create_payment_link

# ===== CONSTANT =====
POLICY_URL = "https://www.roleprep.in/privacy"


# =========================
# PAYMENT REQUEST (called from bot)
# =========================
def handle_payment_request(user_id: str, plan_type: str):
    payment_link = create_payment_link(user_id, plan_type)

    return {
        "status": "pending",
        "payment_link": payment_link,
    }
