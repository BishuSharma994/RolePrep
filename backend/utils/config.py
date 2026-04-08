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


OPENAI_API_KEY = get_clean("OPENAI_API_KEY")
REDIS_URL = get_clean("REDIS_URL")

RAZORPAY_KEY = get_clean("RAZORPAY_KEY") or get_clean("RAZORPAY_KEY_ID")
RAZORPAY_SECRET = get_clean("RAZORPAY_SECRET") or get_clean("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = get_clean("RAZORPAY_WEBHOOK_SECRET")


if not OPENAI_API_KEY:
    raise ValueError(f"Missing OPENAI_API_KEY | searched: {env_search_paths()}")

# Optional
# if not REDIS_URL:
#     raise ValueError("Missing REDIS_URL")
