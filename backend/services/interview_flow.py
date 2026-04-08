import time

from backend.handlers.interview_handler import get_session
from backend.user_store import get_user, set_user_state

DISCLAIMER_TEXT = "Note: It is recommended to complete the interview in one go for best results."


def normalize_paid_plan(plan: str) -> str:
    raw_plan = str(plan or "").strip()
    if raw_plan == "premium":
        return "premium"
    return "session"


def normalize_selected_plan(plan: str) -> str:
    raw_plan = str(plan or "").strip()
    if raw_plan == "premium":
        return "premium"
    if raw_plan == "session_29":
        return "session_29"
    return "session_10"


def activate_paid_session(user_id: str, plan: str):
    user_id = str(user_id)
    now = int(time.time())
    raw_plan = normalize_selected_plan(plan)
    session_plan = normalize_paid_plan(raw_plan)

    set_user_state(
        user_id,
        {
            "active_session": True,
            "active_session_plan": session_plan,
            "current_session_plan": session_plan,
            "selected_plan": raw_plan,
            "session_access": 0,
            "session_started_at": now,
            "last_session_activity_at": now,
        },
    )


def activate_existing_access(user_id: str):
    user = get_user(user_id)

    if user.get("active_session"):
        return

    if int(user.get("subscription_expiry", 0) or 0) > int(time.time()):
        activate_paid_session(user_id, "premium")
        return

    if int(user.get("session_credits", 0) or 0) > 0:
        activate_paid_session(user_id, user.get("selected_plan") or "session_10")


def get_interview_entry(user_id: str) -> dict:
    session = get_session(user_id)

    if session:
        current_question = session.get("current_question") or "Reply with your answer to continue the interview."
        return {
            "state": "resume_session",
            "text": f"Resuming your interview.\n\n{current_question}",
        }

    return {
        "state": "create_session",
        "text": "Create a session with POST /api/sessions.",
    }
