import json
from backend.db.redis_client import r

MAX_QUESTIONS = 5

def create_session(user_id, role, jd_text):
    session = {
        "role": role,
        "jd_text": jd_text,
        "questions_asked": 0,
        "history": []
    }
    r.set(f"session:{user_id}", json.dumps(session))


def get_session(user_id):
    data = r.get(f"session:{user_id}")
    return json.loads(data) if data else None


def update_session(user_id, session):
    r.set(f"session:{user_id}", json.dumps(session))


def end_session(user_id):
    r.delete(f"session:{user_id}")