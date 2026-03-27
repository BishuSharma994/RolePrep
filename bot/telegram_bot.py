from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters
)

from backend.config import TELEGRAM_BOT_TOKEN
from bot.handlers.start import start
from bot.handlers.interview import interview

app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

# Commands
app.add_handler(CommandHandler("start", start))

# All text messages go to interview handler (state-driven)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, interview))


async def startup():
    if not app.running:
        await app.initialize()
        await app.start()


async def shutdown():
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
