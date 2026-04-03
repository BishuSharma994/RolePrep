from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from backend.services.activity import update_user_last_active
from backend.services.feedback import save_feedback

user_state = {}
pending_feedback = {}


def build_feedback_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⭐ 1", callback_data="feedback_1"),
                InlineKeyboardButton("⭐ 2", callback_data="feedback_2"),
                InlineKeyboardButton("⭐ 3", callback_data="feedback_3"),
                InlineKeyboardButton("⭐ 4", callback_data="feedback_4"),
                InlineKeyboardButton("⭐ 5", callback_data="feedback_5"),
            ]
        ]
    )


def save_temp_rating(user_id, rating, session_id):
    pending_feedback[str(user_id)] = {
        "rating": int(rating),
        "session_id": str(session_id),
    }


def clear_feedback_state(user_id):
    user_id = str(user_id)
    user_state.pop(user_id, None)
    pending_feedback.pop(user_id, None)


async def prompt_for_feedback(message, context, user_id, session_id):
    user_id = str(user_id)
    update_user_last_active(user_id)
    context.user_data["pending_feedback_session_id"] = str(session_id)
    pending_feedback[user_id] = {"session_id": str(session_id)}
    user_state.pop(user_id, None)
    await message.reply_text(
        "Interview completed. Please rate your experience",
        reply_markup=build_feedback_keyboard(),
    )


async def handle_feedback_rating(update, context):
    query = update.callback_query
    user_id = str(query.from_user.id)
    update_user_last_active(user_id)
    data = query.data or ""

    if not data.startswith("feedback_"):
        return

    rating = int(data.split("_")[1])
    session_id = (
        context.user_data.get("pending_feedback_session_id")
        or pending_feedback.get(user_id, {}).get("session_id")
    )

    if not session_id:
        clear_feedback_state(user_id)
        context.user_data.pop("pending_feedback_session_id", None)
        await query.answer("No active feedback session found.", show_alert=True)
        return

    save_temp_rating(user_id, rating, session_id)
    user_state[user_id] = "awaiting_feedback_comment"
    context.user_data["pending_feedback_session_id"] = str(session_id)
    await query.answer("Rating received")
    await query.message.reply_text("What could be improved?")


async def handle_feedback_comment(update, context):
    message = update.message
    user_id = str(message.from_user.id)
    update_user_last_active(user_id)

    if user_state.get(user_id) != "awaiting_feedback_comment":
        return False

    comment = (message.text or "").strip()
    if not comment:
        await message.reply_text("What could be improved?")
        return True

    feedback_context = pending_feedback.get(user_id) or {}
    rating = feedback_context.get("rating")
    session_id = feedback_context.get("session_id") or context.user_data.get("pending_feedback_session_id")

    if rating is None or not session_id:
        clear_feedback_state(user_id)
        context.user_data.pop("pending_feedback_session_id", None)
        await message.reply_text("Feedback session expired. Please complete another interview to rate it.")
        return True

    save_feedback(user_id, rating, comment, session_id)
    clear_feedback_state(user_id)
    context.user_data.pop("pending_feedback_session_id", None)
    await message.reply_text("Thanks for your feedback. It helps improve your interview experience.")
    return True
