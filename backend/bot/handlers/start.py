from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from backend.handlers.payment_handler import POLICY_URL, handle_payment_request
from backend.handlers.plan_handler import get_plan, set_plan
from backend.services.plan_manager import get_session_credits, is_subscription_active


def build_plan_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Free Plan", callback_data="select_plan:free")],
            [InlineKeyboardButton("Session ₹1", callback_data="select_plan:session")],
            [InlineKeyboardButton("Premium ₹2", callback_data="select_plan:subscription")],
        ]
    )


def _has_plan_access(user_id: str, plan_type: str) -> bool:
    if plan_type == "subscription":
        return is_subscription_active(user_id)

    if plan_type == "session":
        return get_session_credits(user_id) > 0

    return True


async def start(update, context):
    selected_plan = get_plan(str(update.effective_user.id))

    context.user_data.clear()
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
    plan_type = query.data.split(":", 1)[1]

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
        context.user_data["state"] = "ASK_ROLE"
        await query.answer("Plan unlocked")
        await query.edit_message_text(
            "Plan already active.\n\n"
            "Step 1: Enter the role you are applying for."
        )
        return

    payment_result = handle_payment_request(user_id, plan_type)
    context.user_data["state"] = "AWAITING_PAYMENT"

    label = "Premium" if plan_type == "subscription" else "Session Plan"

    await query.answer("Payment required")
    await query.edit_message_text(
        f"{label} selected.\n\n"
        f"Complete payment here: {payment_result['payment_link']}\n\n"
        "After successful payment confirmation, send /start and select your plan again."
    )


async def policy_command(update, context):
    await update.message.reply_text(
        f'Read full policy:\n<a href="{POLICY_URL}">Policy &amp; Terms</a>',
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
