from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from backend.handlers.payment_handler import POLICY_URL, handle_payment_request
from backend.handlers.plan_handler import get_plan, set_plan
from backend.rate_limit import allow_request
from backend.services.interview_flow import (
    DISCLAIMER_TEXT,
    activate_existing_access,
    get_interview_entry,
    sync_context_with_user_state,
)
from backend.services.plan_manager import get_session_credits, is_subscription_active
from backend.user_store import get_user, get_user_state


def build_plan_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Free Plan", callback_data="select_plan:free")],
            [InlineKeyboardButton("1 Session Rs10", callback_data="select_plan:session_10")],
            [InlineKeyboardButton("5 Sessions Rs29", callback_data="select_plan:session_29")],
            [InlineKeyboardButton("Premium Rs99", callback_data="select_plan:premium")],
        ]
    )


def _has_plan_access(user_id: str, plan_type: str) -> bool:
    if plan_type == "premium":
        return is_subscription_active(user_id)

    if plan_type in {"session", "session_10", "session_29"}:
        return get_session_credits(user_id) > 0

    return True


async def start(update, context):
    user_id = str(update.effective_user.id)
    if not allow_request(user_id):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Too many requests. Please slow down.",
        )
        return

    context.user_data.clear()

    activate_existing_access(user_id)
    user = get_user(user_id)

    if user.get("active_session") or is_subscription_active(user_id) or get_session_credits(user_id) > 0:
        activate_existing_access(user_id)
        sync_context_with_user_state(context, user_id)
        entry = get_interview_entry(user_id)
        context.user_data["state"] = entry["state"]

        await update.message.reply_text(DISCLAIMER_TEXT)
        await update.message.reply_text(entry["text"])
        return

    selected_plan = get_plan(user_id)
    context.user_data["state"] = None

    if selected_plan:
        context.user_data["selected_plan"] = selected_plan

    await update.message.reply_text(
        "Welcome to RolePrep.\n\n"
        "You are on Free Tier:\n"
        "- 1 session/day\n"
        "- 5 questions\n\n"
        "Upgrade for full access.\n\n"
        f'<a href="{POLICY_URL}">Policy &amp; Terms</a>',
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=build_plan_keyboard(),
    )


async def handle_plan_selection(update, context):
    query = update.callback_query
    user_id = str(query.from_user.id)
    if not allow_request(user_id):
        await query.answer("Too many requests. Please slow down.", show_alert=True)
        return

    raw_plan = query.data.split(":", 1)[1]

    plan_map = {
        "free": "free",
        "session_10": "session_10",
        "session_29": "session_29",
        "premium": "premium",
    }

    plan_type = plan_map.get(raw_plan)

    set_plan(user_id, plan_type)
    context.user_data["selected_plan"] = plan_type

    if plan_type == "free":
        context.user_data["state"] = "ASK_ROLE"
        await query.answer("Free plan selected")
        await query.edit_message_text(
            "Free Plan selected.\n\n"
            "You can use 1 session per day and 5 questions.\n\n"
            "Step 1: Enter the role you are applying for."
        )
        return

    if _has_plan_access(user_id, plan_type):
        activate_existing_access(user_id)
        sync_context_with_user_state(context, user_id)
        entry = get_interview_entry(user_id)
        context.user_data["state"] = entry["state"]
        await query.answer("Plan unlocked")
        await query.edit_message_text(
            f"{DISCLAIMER_TEXT}\n\n{entry['text']}"
        )
        return

    payment_result = handle_payment_request(user_id, plan_type)
    context.user_data["state"] = "AWAITING_PAYMENT"

    if plan_type == "premium":
        label = "Premium"
    elif plan_type == "session_29":
        label = "5 Session Pack"
    else:
        label = "1 Session Pack"

    await query.answer("Payment required")
    await query.edit_message_text(
        f"{label} selected.\n\n"
        f"Complete payment here: {payment_result['payment_link']}\n\n"
        "Your interview will start automatically after payment confirmation."
    )


async def policy_command(update, context):
    user_id = str(update.effective_user.id)
    if not allow_request(user_id):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Too many requests. Please slow down.",
        )
        return

    await update.message.reply_text(
        f'Read full policy:\n<a href="{POLICY_URL}">Policy &amp; Terms</a>',
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


def handle_status(user_id):
    state = get_user_state(user_id)

    if state["is_premium"]:
        return (
            f"Premium Active ({state['days_left']} days left)\n"
            f"Credits available: {state['credits']}\n"
            f"Active session: {'Yes' if state['active_session'] else 'No'}"
        )

    return (
        f"Free Plan\n"
        f"Credits available: {state['credits']}\n"
        f"Active session: {'Yes' if state['active_session'] else 'No'}"
    )


async def status_command(update, context):
    user_id = str(update.effective_user.id)
    if not allow_request(user_id):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Too many requests. Please slow down.",
        )
        return

    message = handle_status(user_id)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
    )
