import redis
from backend.utils.config import REDIS_URL

r = redis.from_url(REDIS_URL, decode_responses=True)

try:
    r.ping()
except Exception:
    raise
