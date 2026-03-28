from datetime import datetime, timedelta

STORE = {}


def get_today_key(user_id: str) -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return f"{user_id}:{today}"


def get_user_plan(user_id: str) -> str:
    if is_subscription_active(user_id):
        return "subscription"
    return STORE.get(f"{user_id}:plan", "free")


def set_user_plan(user_id: str, plan: str):
    STORE[f"{user_id}:plan"] = plan


def increment_usage(user_id: str):
    start_mode = STORE.get(f"{user_id}:session_access")
    if start_mode != "free":
        return

    key = get_today_key(user_id)
    STORE[key] = STORE.get(key, 0) + 1


def get_usage(user_id: str) -> int:
    key = get_today_key(user_id)
    return STORE.get(key, 0)


def add_session_credits(user_id: str, credits: int):
    key = f"{user_id}:session_credits"
    STORE[key] = STORE.get(key, 0) + credits


def get_session_credits(user_id: str) -> int:
    return STORE.get(f"{user_id}:session_credits", 0)


def use_session_credit(user_id: str) -> bool:
    key = f"{user_id}:session_credits"
    credits = STORE.get(key, 0)
    if credits <= 0:
        return False

    STORE[key] = credits - 1
    return True


def activate_subscription(user_id: str, days: int):
    STORE[f"{user_id}:subscription_expires_at"] = datetime.utcnow() + timedelta(days=days)
    STORE[f"{user_id}:plan"] = "subscription"


def is_subscription_active(user_id: str) -> bool:
    expiry = STORE.get(f"{user_id}:subscription_expires_at")
    if not expiry:
        return False

    if expiry > datetime.utcnow():
        return True

    STORE[f"{user_id}:plan"] = "free"
    return False


def can_start_session(user_id: str) -> bool:
    if is_subscription_active(user_id):
        STORE[f"{user_id}:session_access"] = "subscription"
        return True

    if use_session_credit(user_id):
        STORE[f"{user_id}:session_access"] = "credit"
        return True

    if get_usage(user_id) < 1:
        STORE[f"{user_id}:session_access"] = "free"
        return True

    return False


def get_current_access_mode(user_id: str) -> str:
    if is_subscription_active(user_id):
        return "subscription"
    return STORE.get(f"{user_id}:session_access", "free")


def clear_session_access(user_id: str):
    STORE.pop(f"{user_id}:session_access", None)


def can_ask_question(user_id: str, current_q_count: int) -> bool:
    if get_current_access_mode(user_id) == "free":
        return current_q_count < 5
    return True
