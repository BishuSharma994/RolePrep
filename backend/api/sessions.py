from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.handlers.interview_handler import get_session, start_interview
from backend.services.db import users
from backend.user_store import get_user, resolve_plan

router = APIRouter()


class SessionCreateRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    jd_text: str = Field(..., min_length=1)
    parser_data: dict[str, Any] = Field(default_factory=dict)
    resume_path: str | None = None
    jd_path: str | None = None


def _visible_plan(user: dict[str, Any]) -> str | None:
    active_plan = user.get("active_session_plan") or user.get("current_session_plan")
    if active_plan:
        return str(active_plan)

    resolved_plan = resolve_plan(user)
    return None if resolved_plan == "free" else str(resolved_plan)


def _serialize_session(user_id: str, session: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(user_id),
        "session_id": session.get("session_id"),
        "role": session.get("role", ""),
        "jd_text": session.get("jd_text", ""),
        "current_question": session.get("current_question"),
        "current_stage": session.get("current_stage"),
        "question_count": int(session.get("question_count", 0) or 0),
        "history": list(session.get("history", [])),
        "scores": list(session.get("scores", [])),
        "active_session": bool(user.get("active_session", False)),
        "active_session_plan": _visible_plan(user),
        "session_credits": int(user.get("session_credits", 0) or 0),
        "subscription_expiry": int(user.get("subscription_expiry", 0) or 0),
        "selected_plan": user.get("selected_plan", "free"),
        "session_started_at": user.get("session_started_at"),
        "last_session_activity_at": user.get("last_session_activity_at"),
        "updated_at": session.get("last_question_ts"),
    }


def _serialize_session_document(document: dict[str, Any]) -> dict[str, Any]:
    visible_plan = document.get("active_session_plan") or document.get("current_session_plan")
    if not visible_plan:
        if int(document.get("subscription_expiry", 0) or 0) > 0:
            visible_plan = "premium"
        elif int(document.get("session_credits", 0) or 0) > 0:
            visible_plan = "session"

    return {
        "user_id": str(document.get("user_id") or ""),
        "session_id": document.get("session_id"),
        "role": document.get("session_role", ""),
        "jd_text": document.get("session_jd_text", ""),
        "current_question": document.get("current_question"),
        "current_stage": document.get("current_stage"),
        "question_count": int(document.get("session_question_count", 0) or 0),
        "history": list(document.get("session_history", [])),
        "scores": list(document.get("session_scores", [])),
        "active_session": bool(document.get("active_session", False)),
        "active_session_plan": visible_plan,
        "session_credits": int(document.get("session_credits", 0) or 0),
        "subscription_expiry": int(document.get("subscription_expiry", 0) or 0),
        "selected_plan": document.get("selected_plan", "free"),
        "session_started_at": document.get("session_started_at"),
        "last_session_activity_at": document.get("last_session_activity_at"),
        "updated_at": document.get("updated_at"),
    }


@router.post("/sessions")
async def create_session(payload: SessionCreateRequest):
    result = start_interview(
        user_id=str(payload.user_id),
        role=str(payload.role),
        jd_text=str(payload.jd_text),
        parser_data=payload.parser_data,
        resume_path=payload.resume_path,
        jd_path=payload.jd_path,
    )

    if result.get("status") != "started":
        raise HTTPException(status_code=403, detail=result)

    session = get_session(str(payload.user_id))
    if not session:
        raise HTTPException(status_code=500, detail="Session was created but could not be loaded")

    user = get_user(str(payload.user_id))
    return {
        "status": "started",
        "session": _serialize_session(str(payload.user_id), session, user),
    }


@router.get("/sessions")
async def list_sessions(
    user_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    if user_id:
        session = get_session(str(user_id))
        if not session:
            return {"sessions": []}
        user = get_user(str(user_id))
        return {"sessions": [_serialize_session(str(user_id), session, user)]}

    projection = {
        "_id": 0,
        "user_id": 1,
        "session_id": 1,
        "session_role": 1,
        "session_jd_text": 1,
        "current_question": 1,
        "current_stage": 1,
        "session_question_count": 1,
        "session_history": 1,
        "session_scores": 1,
        "active_session": 1,
        "active_session_plan": 1,
        "current_session_plan": 1,
        "session_credits": 1,
        "subscription_expiry": 1,
        "selected_plan": 1,
        "session_started_at": 1,
        "last_session_activity_at": 1,
        "updated_at": 1,
    }
    documents = list(
        users.find({"active_session": True}, projection).sort("last_session_activity_at", -1).limit(int(limit))
    )
    return {"sessions": [_serialize_session_document(document) for document in documents]}
