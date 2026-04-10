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


def get_bool(key, default: bool = False) -> bool:
    value = get_clean(key)
    if value is None:
        return bool(default)
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int(key, default: int) -> int:
    value = get_clean(key)
    if value is None:
        return int(default)
    try:
        return int(value)
    except ValueError:
        return int(default)


OPENAI_API_KEY = get_clean("OPENAI_API_KEY")
REDIS_URL = get_clean("REDIS_URL")
FRONTEND_APP_URL = get_clean("FRONTEND_APP_URL") or "https://www.roleprep.in"

RAZORPAY_KEY = get_clean("RAZORPAY_KEY") or get_clean("RAZORPAY_KEY_ID")
RAZORPAY_SECRET = get_clean("RAZORPAY_SECRET") or get_clean("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = get_clean("RAZORPAY_WEBHOOK_SECRET")
AUTH_REQUIRE_WEB_API = get_bool("AUTH_REQUIRE_WEB_API", default=False)
AUTH_DEBUG_OTP = get_bool("AUTH_DEBUG_OTP", default=False)
AUTH_OTP_TTL_SECONDS = get_int("AUTH_OTP_TTL_SECONDS", default=600)
AUTH_SESSION_TTL_SECONDS = get_int("AUTH_SESSION_TTL_SECONDS", default=2592000)
AUTH_OTP_RESEND_COOLDOWN_SECONDS = get_int("AUTH_OTP_RESEND_COOLDOWN_SECONDS", default=60)
AUTH_SMTP_HOST = get_clean("AUTH_SMTP_HOST")
AUTH_SMTP_PORT = get_int("AUTH_SMTP_PORT", default=587)
AUTH_SMTP_USERNAME = get_clean("AUTH_SMTP_USERNAME")
AUTH_SMTP_PASSWORD = get_clean("AUTH_SMTP_PASSWORD")
AUTH_SMTP_FROM_EMAIL = get_clean("AUTH_SMTP_FROM_EMAIL")
ZEPTO_API_HOST = get_clean("ZEPTO_API_HOST")
ZEPTO_API_URL = get_clean("ZEPTO_API_URL")
ZEPTO_SEND_MAIL_TOKEN = get_clean("ZEPTO_SEND_MAIL_TOKEN")
ZEPTO_FROM_EMAIL = get_clean("ZEPTO_FROM_EMAIL")
ZEPTO_FROM_NAME = get_clean("ZEPTO_FROM_NAME") or "RolePrep"


if not OPENAI_API_KEY:
    raise ValueError(f"Missing OPENAI_API_KEY | searched: {env_search_paths()}")

# Optional
# if not REDIS_URL:
#     raise ValueError("Missing REDIS_URL")
