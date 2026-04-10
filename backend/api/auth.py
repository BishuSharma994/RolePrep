from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


class RequestOtpPayload(BaseModel):
    email: str = Field(..., min_length=3)


class VerifyOtpPayload(BaseModel):
    email: str = Field(..., min_length=3)
    otp: str = Field(..., min_length=4)
    user_id: str | None = None


def _request_email_otp(email: str):
    from backend.auth_service import AuthError, request_email_otp

    try:
        return request_email_otp(email)
    except AuthError:
        raise


def _verify_email_otp(email: str, otp: str, user_id: str | None):
    from backend.auth_service import AuthError, verify_email_otp

    try:
        return verify_email_otp(email=email, otp=otp, current_user_id=user_id)
    except AuthError:
        raise


def _get_auth_session_from_header(authorization: str | None):
    from backend.auth_service import AuthError, get_auth_session_from_header

    try:
        return get_auth_session_from_header(authorization)
    except AuthError:
        raise


def _revoke_auth_session(authorization: str | None):
    from backend.auth_service import AuthError, revoke_auth_session

    try:
        revoke_auth_session(authorization)
    except AuthError:
        raise


@router.post("/auth/request-otp")
async def request_otp(payload: RequestOtpPayload):
    from backend.auth_service import AuthError

    try:
        return _request_email_otp(str(payload.email))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/auth/config")
async def auth_config():
    from backend.auth_service import otp_delivery_configured
    from backend.utils.config import AUTH_DEBUG_OTP, AUTH_REQUIRE_WEB_API

    otp_login_enabled = bool(AUTH_DEBUG_OTP or otp_delivery_configured())
    return {
        "status": "ok",
        "auth_required": bool(AUTH_REQUIRE_WEB_API),
        "anonymous_mode_allowed": not bool(AUTH_REQUIRE_WEB_API),
        "otp_login_enabled": otp_login_enabled,
        "account_sync_enabled": True,
    }


@router.post("/auth/verify-otp")
async def verify_otp(payload: VerifyOtpPayload):
    from backend.auth_service import AuthError

    try:
        return _verify_email_otp(
            email=str(payload.email),
            otp=str(payload.otp),
            user_id=str(payload.user_id).strip() if payload.user_id else None,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/auth/session")
async def get_auth_session(request: Request):
    from backend.auth_service import AuthError

    try:
        session = _get_auth_session_from_header(request.headers.get("authorization"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")

    return {
        "status": "authenticated",
        "user_id": str(session.get("user_id") or ""),
        "email": str(session.get("email") or ""),
        "expires_at": int(session.get("expires_at", 0) or 0),
    }


@router.post("/auth/logout")
async def logout(request: Request):
    from backend.auth_service import AuthError

    try:
        _revoke_auth_session(request.headers.get("authorization"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return {"status": "logged_out"}
