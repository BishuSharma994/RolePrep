import redis
from backend.config import REDIS_URL

r = redis.from_url(REDIS_URL, decode_responses=True)

try:
    r.ping()
    print("Redis connected")
except Exception as e:
    print("Redis connection failed:", e)
    raise