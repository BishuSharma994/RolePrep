from datetime import datetime

from fastapi import APIRouter, Request

from backend.services.db import db

router = APIRouter()


@router.post("/track")
async def track_event(req: Request):
    body = await req.json()

    event_doc = {
        "user_id": body.get("user_id"),
        "event": body.get("event"),
        "meta": body.get("data", {}),
        "timestamp": datetime.utcnow(),
    }

    db.events.insert_one(event_doc)

    return {"status": "ok"}
