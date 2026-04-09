from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from backend.services.db import db

router = APIRouter()


def _resolve_request_user_id(user_id: str | None, authorization: str | None) -> str:
    from backend.auth_service import AuthError, resolve_request_user_id

    try:
        return resolve_request_user_id(user_id, authorization)
    except AuthError:
        raise


@router.post("/track")
async def track_event(req: Request):
    from backend.auth_service import AUTH_REQUIRE_WEB_API, AuthError

    body = await req.json()
    raw_user_id = body.get("user_id")
    resolved_user_id = raw_user_id

    has_auth_header = bool(str(req.headers.get("authorization") or "").strip())
    if raw_user_id or has_auth_header or AUTH_REQUIRE_WEB_API:
        try:
            resolved_user_id = _resolve_request_user_id(raw_user_id, req.headers.get("authorization"))
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    event_doc = {
        "user_id": resolved_user_id,
        "event": body.get("event"),
        "meta": body.get("data", {}),
        "timestamp": datetime.utcnow(),
    }

    db.events.insert_one(event_doc)

    return {"status": "ok"}
