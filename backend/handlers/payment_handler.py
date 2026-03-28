from backend.services.payment import create_payment_link
from backend.services.plan_manager import add_session_credits, activate_subscription

POLICY_URL = "https://github.com/BishuSharma994/RolePrep/blob/main/POLICY.md"


def handle_payment_request(user_id, plan_type):
    return {
        "status": "policy_required",
        "message": "Please review and accept policy before payment",
        "plan": plan_type,
        "policy_url": POLICY_URL,
    }


def create_payment_after_consent(user_id, plan_type, policy_accepted):
    if not policy_accepted:
        raise ValueError("Policy acceptance required before payment")

    payment_link = create_payment_link(user_id, plan_type)
    return {
        "status": "payment_required",
        "plan": plan_type,
        "payment_link": payment_link,
    }


def confirm_payment(user_id, plan_type):
    if plan_type == "session":
        add_session_credits(user_id, 1)
    elif plan_type == "subscription":
        activate_subscription(user_id, 30)
    else:
        raise ValueError("Unsupported plan_type")

    return {
        "status": "payment_confirmed",
        "plan": plan_type,
    }
