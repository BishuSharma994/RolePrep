import os
from dotenv import dotenv_values

config = dotenv_values(".env")


# Defensive read (strip + fallback)
def get_clean(key):
    v = config.get(key)

    if v is None:
        for k in config.keys():
            if k.strip().upper() == key:
                v = config.get(k)
                break

    if isinstance(v, str):
        v = v.strip()

    return v


TELEGRAM_BOT_TOKEN = get_clean("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_URL = get_clean("TELEGRAM_WEBHOOK_URL")
OPENAI_API_KEY = get_clean("OPENAI_API_KEY")
REDIS_URL = get_clean("REDIS_URL")


# VALIDATION ONLY (NO PRINTS)
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN")

if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY")

if not REDIS_URL:
    raise ValueError("Missing REDIS_URL")
