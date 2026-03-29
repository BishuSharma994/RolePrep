from backend.services.plan_manager import (
    get_session_credits,
    is_subscription_active,
)

PLAN_SELECTIONS = {}


def set_plan(user_id, plan_type):
    # store last selected (UI intent only)
    PLAN_SELECTIONS[user_id] = plan_type
    return plan_type


def get_plan(user_id):
    # --- PRIORITY: PREMIUM ---
    if is_subscription_active(user_id):
        return "premium"

    # --- THEN SESSION ---
    if get_session_credits(user_id) > 0:
        return "session"

    # --- FALLBACK: UI SELECTION ---
    return PLAN_SELECTIONS.get(user_id, "free")