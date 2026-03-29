from backend.services.plan_manager import (
    get_session_credits,
    is_subscription_active,
    set_user_plan,
)
from backend.user_store import get_user

def set_plan(user_id, plan_type):
    set_user_plan(user_id, plan_type)
    return plan_type


def get_plan(user_id):
    if is_subscription_active(user_id):
        return "premium"

    if get_session_credits(user_id) > 0:
        return "session"

    user = get_user(user_id)
    return user.get("selected_plan", "free")
