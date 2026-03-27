from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters
)

from backend.config import TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_URL
from bot.handlers.start import start
from bot.handlers.interview import interview

app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
RUN_MODE = "polling"

# Commands
app.add_handler(CommandHandler("start", start))

# All text messages go to interview handler (state-driven)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, interview))


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
    print("Bot running...")
    app.run_polling()
