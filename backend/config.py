import os
from dotenv import dotenv_values

config = dotenv_values(".env")

print("CONFIG RAW:", config)
print("KEYS:", list(config.keys()))

# Defensive read (strip + fallback)
def get_clean(key):
    v = config.get(key)
    if v is None:
        # try case/whitespace variants
        for k in config.keys():
            if k.strip().upper() == key:
                v = config.get(k)
                break
    if isinstance(v, str):
        v = v.strip()
    return v

TELEGRAM_BOT_TOKEN = get_clean("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = get_clean("OPENAI_API_KEY")
REDIS_URL = get_clean("REDIS_URL")

print("TOKEN AFTER CLEAN:", TELEGRAM_BOT_TOKEN)

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN")

if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY")

if not REDIS_URL:
    raise ValueError("Missing REDIS_URL")