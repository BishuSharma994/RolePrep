from dotenv import dotenv_values
import os

# Absolute path to .env (no dependency on working directory)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")

config = dotenv_values(ENV_PATH)


def get_clean(key):
    value = config.get(key)

    if value is None:
        for config_key in config.keys():
            if config_key.strip().upper() == key:
                value = config.get(config_key)
                break

    if isinstance(value, str):
        value = value.strip()

    return value


TELEGRAM_BOT_TOKEN = get_clean("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_URL = get_clean("TELEGRAM_WEBHOOK_URL")
OPENAI_API_KEY = get_clean("OPENAI_API_KEY")
REDIS_URL = get_clean("REDIS_URL")

RAZORPAY_KEY = get_clean("RAZORPAY_KEY") or get_clean("RAZORPAY_KEY_ID")
RAZORPAY_SECRET = get_clean("RAZORPAY_SECRET") or get_clean("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = get_clean("RAZORPAY_WEBHOOK_SECRET")


# Strict validation (only for required services)
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN")

if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY")

# Optional: disable strict check if not using Redis yet
# if not REDIS_URL:
#     raise ValueError("Missing REDIS_URL")