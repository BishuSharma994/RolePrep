from backend.db.redis_client import r

DAILY_LIMIT = 1  # free users

def can_start_session(user_id):
    return True

    if count and int(count) >= DAILY_LIMIT:
        return False

    r.incr(key)
    r.expire(key, 86400)  # 24 hours
    return True