from telegram import Update
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from backend.bot.handlers.feedback import handle_feedback_rating
from backend.bot.handlers.interview import interview
from backend.bot.handlers.start import handle_plan_selection, policy_command, start, status_command
from backend.utils.config import TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL

app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
RUN_MODE = "polling"

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("status", status_command))
app.add_handler(CommandHandler("policy", policy_command))
app.add_handler(CallbackQueryHandler(handle_feedback_rating, pattern=r"^feedback_[1-5]$"))
app.add_handler(CallbackQueryHandler(handle_plan_selection, pattern=r"^select_plan:"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, interview))
app.add_handler(MessageHandler(filters.Document.PDF, interview))


async def startup():
    global RUN_MODE

    if app.running:
        return

    await app.initialize()
    await app.start()

    if TELEGRAM_WEBHOOK_URL:
        webhook_url = f"{TELEGRAM_WEBHOOK_URL.rstrip('/')}/webhook/telegram"
        await app.bot.set_webhook(webhook_url)
        RUN_MODE = "webhook"
        return

    if app.updater and not app.updater.running:
        await app.updater.start_polling()
    RUN_MODE = "polling"


async def shutdown():
    if app.updater and app.updater.running:
        await app.updater.stop()

    if app.running:
        await app.stop()

    if app._initialized:
        await app.shutdown()


async def process_update(data):
    update = Update.de_json(data, app.bot)
    await app.process_update(update)


if __name__ == "__main__":
    app.run_polling()
