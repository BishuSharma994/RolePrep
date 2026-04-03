from datetime import datetime

from backend.services.db import feedbacks, users
from backend.utils.logger import log_event


def save_feedback(user_id, rating, comment, session_id):
    user_id = str(user_id)
    rating = int(rating)
    comment = str(comment or "").strip()
    session_id = str(session_id)

    user = users.find_one({"user_id": user_id}, {"selected_plan": 1, "_id": 0}) or {}
    plan = user.get("selected_plan")

    payload = {
        "user_id": user_id,
        "rating": rating,
        "comment": comment,
        "session_id": session_id,
        "created_at": datetime.utcnow(),
    }
    if plan:
        payload["plan"] = plan

    result = feedbacks.insert_one(payload)
    if not result.acknowledged:
        raise RuntimeError(f"Failed to save feedback for session {session_id}")

    log_event(
        "feedback_saved",
        {
            "user_id": user_id,
            "rating": rating,
            "session_id": session_id,
            "plan": plan,
        },
    )

    if rating <= 2:
        log_event(
            "feedback_low_rating",
            {
                "user_id": user_id,
                "rating": rating,
                "session_id": session_id,
                "comment": comment,
                "plan": plan,
            },
        )

    return payload


def get_average_rating():
    pipeline = [
        {
            "$group": {
                "_id": None,
                "average_rating": {"$avg": "$rating"},
                "total_feedbacks": {"$sum": 1},
            }
        }
    ]
    result = list(feedbacks.aggregate(pipeline))
    if not result:
        return {"average_rating": 0, "total_feedbacks": 0}
    return {
        "average_rating": round(float(result[0].get("average_rating", 0) or 0), 2),
        "total_feedbacks": int(result[0].get("total_feedbacks", 0) or 0),
    }


def get_feedback_count_per_plan():
    pipeline = [
        {
            "$group": {
                "_id": "$plan",
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1}},
    ]
    return [
        {"plan": row.get("_id") or "unknown", "count": int(row.get("count", 0) or 0)}
        for row in feedbacks.aggregate(pipeline)
    ]


def get_low_rating_feedbacks():
    return list(
        feedbacks.find(
            {"rating": {"$lte": 2}},
            {"_id": 0},
        ).sort("created_at", -1)
    )
