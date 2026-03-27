from datetime import datetime

STORE = {}


def get_today_key(user_id: str) -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return f"{user_id}:{today}"


def get_user_plan(user_id: str) -> str:
    return STORE.get(f"{user_id}:plan", "free")


def set_user_plan(user_id: str, plan: str):
    STORE[f"{user_id}:plan"] = plan


def increment_usage(user_id: str):
    key = get_today_key(user_id)
    STORE[key] = STORE.get(key, 0) + 1


def get_usage(user_id: str) -> int:
    key = get_today_key(user_id)
    return STORE.get(key, 0)


def can_start_session(user_id: str) -> bool:
    if get_user_plan(user_id) == "free":
        return get_usage(user_id) < 1
    return True


def can_ask_question(user_id: str, current_q_count: int) -> bool:
    if get_user_plan(user_id) == "free":
        return current_q_count < 5
    return True