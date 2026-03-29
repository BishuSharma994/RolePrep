from backend.utils.env_loader import (
    env_search_paths,
    get_env_value,
    load_environment,
    merged_env_values,
)

load_environment()
config = merged_env_values()


def get_clean(key):
    return get_env_value(key, fallback=config)


TELEGRAM_BOT_TOKEN = get_clean("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_URL = get_clean("TELEGRAM_WEBHOOK_URL")
OPENAI_API_KEY = get_clean("OPENAI_API_KEY")
REDIS_URL = get_clean("REDIS_URL")

RAZORPAY_KEY = get_clean("RAZORPAY_KEY") or get_clean("RAZORPAY_KEY_ID")
RAZORPAY_SECRET = get_clean("RAZORPAY_SECRET") or get_clean("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = get_clean("RAZORPAY_WEBHOOK_SECRET")


# Strict validation
if not TELEGRAM_BOT_TOKEN:
    raise ValueError(f"Missing TELEGRAM_BOT_TOKEN | searched: {env_search_paths()}")

if not OPENAI_API_KEY:
    raise ValueError(f"Missing OPENAI_API_KEY | searched: {env_search_paths()}")

# Optional
# if not REDIS_URL:
#     raise ValueError("Missing REDIS_URL")
