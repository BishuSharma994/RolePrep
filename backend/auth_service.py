from __future__ import annotations

import hashlib
import re
import secrets
import smtplib
import time
import uuid
from datetime import datetime
from email.message import EmailMessage
from typing import Any

import requests

from backend.utils.config import (
    AUTH_DEBUG_OTP,
    AUTH_OTP_RESEND_COOLDOWN_SECONDS,
    AUTH_OTP_TTL_SECONDS,
    AUTH_REQUIRE_WEB_API,
    AUTH_SESSION_TTL_SECONDS,
    AUTH_SMTP_FROM_EMAIL,
    AUTH_SMTP_HOST,
    AUTH_SMTP_PASSWORD,
    AUTH_SMTP_PORT,
    AUTH_SMTP_USERNAME,
    ZEPTO_API_HOST,
    ZEPTO_API_URL,
    ZEPTO_FROM_EMAIL,
    ZEPTO_FROM_NAME,
    ZEPTO_SEND_MAIL_TOKEN,
)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
OTP_LENGTH = 6
MAX_OTP_ATTEMPTS = 5


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = int(status_code)


def _now() -> int:
    return int(time.time())


def _utcnow() -> datetime:
    return datetime.utcnow()


def _collections():
    from backend.services.db import auth_identities, auth_otps, auth_sessions, users

    return auth_identities, auth_otps, auth_sessions, users


def _ensure_user(user_id: str):
    from backend.user_store import get_user

    return get_user(user_id)


def normalize_email(email: str) -> str:
    normalized = str(email or "").strip().lower()
    if not normalized or not EMAIL_PATTERN.match(normalized):
        raise AuthError("Invalid email address", status_code=400)
    return normalized


def _hash_token(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _generate_otp() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))


def _smtp_configured() -> bool:
    return bool(AUTH_SMTP_HOST and AUTH_SMTP_FROM_EMAIL)


def _zepto_configured() -> bool:
    return bool((ZEPTO_API_URL or ZEPTO_API_HOST) and ZEPTO_SEND_MAIL_TOKEN and ZEPTO_FROM_EMAIL)


def otp_delivery_configured() -> bool:
    return _zepto_configured() or _smtp_configured()


def _zepto_api_url() -> str:
    configured_url = str(ZEPTO_API_URL or "").strip()
    if configured_url:
        return configured_url

    host = str(ZEPTO_API_HOST or "").strip()
    if not host:
        raise AuthError("ZeptoMail API host is not configured", status_code=503)

    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/") + "/v1.1/email"

    return f"https://{host}/v1.1/email"


def _send_otp_via_zepto(email: str, otp: str) -> None:
    if not _zepto_configured():
        raise AuthError("ZeptoMail delivery is not configured", status_code=503)

    response = requests.post(
        _zepto_api_url(),
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": str(ZEPTO_SEND_MAIL_TOKEN),
        },
        json={
            "from": {
                "address": str(ZEPTO_FROM_EMAIL),
                "name": str(ZEPTO_FROM_NAME),
            },
            "to": [
                {
                    "email_address": {
                        "address": str(email),
                    }
                }
            ],
            "subject": "Your RolePrep login code",
            "textbody": (
                f"Your RolePrep login code is {otp}. "
                f"It expires in {max(1, AUTH_OTP_TTL_SECONDS // 60)} minutes."
            ),
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise AuthError(f"ZeptoMail delivery failed: {response.text}", status_code=503)


def _send_otp_email(email: str, otp: str) -> None:
    if _zepto_configured():
        _send_otp_via_zepto(email, otp)
        return

    if not _smtp_configured():
        raise AuthError("OTP email delivery is not configured", status_code=503)

    message = EmailMessage()
    message["Subject"] = "Your RolePrep login code"
    message["From"] = str(AUTH_SMTP_FROM_EMAIL)
    message["To"] = email
    message.set_content(
        "Your RolePrep login code is "
        f"{otp}. It expires in {max(1, AUTH_OTP_TTL_SECONDS // 60)} minutes."
    )

    with smtplib.SMTP(str(AUTH_SMTP_HOST), int(AUTH_SMTP_PORT), timeout=20) as smtp:
        smtp.starttls()
        if AUTH_SMTP_USERNAME:
            smtp.login(str(AUTH_SMTP_USERNAME), str(AUTH_SMTP_PASSWORD or ""))
        smtp.send_message(message)


def request_email_otp(email: str) -> dict[str, Any]:
    normalized_email = normalize_email(email)
    now = _now()
    _, auth_otps, _, _ = _collections()

    existing = auth_otps.find_one(
        {"email": normalized_email, "status": "pending"},
        {"created_at": 1, "expires_at": 1, "_id": 0},
        sort=[("created_at", -1)],
    )
    if existing and now - int(existing.get("created_at", 0) or 0) < AUTH_OTP_RESEND_COOLDOWN_SECONDS:
        raise AuthError("Please wait before requesting another code", status_code=429)

    auth_otps.update_many(
        {"email": normalized_email, "status": "pending"},
        {"$set": {"status": "replaced", "updated_at": now}},
    )

    otp = _generate_otp()
    auth_otps.insert_one(
        {
            "email": normalized_email,
            "otp_hash": _hash_token(f"{normalized_email}:{otp}"),
            "status": "pending",
            "attempts": 0,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + AUTH_OTP_TTL_SECONDS,
        }
    )

    if AUTH_DEBUG_OTP:
        return {
            "status": "sent",
            "email": normalized_email,
            "expires_in_seconds": AUTH_OTP_TTL_SECONDS,
            "debug_otp": otp,
        }

    _send_otp_email(normalized_email, otp)
    return {
        "status": "sent",
        "email": normalized_email,
        "expires_in_seconds": AUTH_OTP_TTL_SECONDS,
    }


def _resolve_canonical_user_id(email: str, current_user_id: str | None) -> str:
    auth_identities, _, _, _ = _collections()
    identity = auth_identities.find_one({"email": email}, {"user_id": 1, "_id": 0}) or {}
    existing_user_id = str(identity.get("user_id") or "").strip()
    if existing_user_id:
        return existing_user_id

    candidate_user_id = str(current_user_id or "").strip() or uuid.uuid4().hex
    _ensure_user(candidate_user_id)
    auth_identities.update_one(
        {"email": email},
        {
            "$setOnInsert": {
                "user_id": candidate_user_id,
                "created_at": _utcnow(),
            },
            "$set": {
                "last_login_at": _utcnow(),
            },
        },
        upsert=True,
    )
    identity = auth_identities.find_one({"email": email}, {"user_id": 1, "_id": 0}) or {}
    resolved_user_id = str(identity.get("user_id") or candidate_user_id).strip()
    return resolved_user_id or candidate_user_id


def _create_auth_session(user_id: str, email: str) -> dict[str, Any]:
    now = _now()
    token = secrets.token_urlsafe(32)
    expires_at = now + AUTH_SESSION_TTL_SECONDS
    _, _, auth_sessions, _ = _collections()
    auth_sessions.insert_one(
        {
            "token_hash": _hash_token(token),
            "user_id": str(user_id),
            "email": str(email),
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "expires_at": expires_at,
        }
    )
    return {
        "token": token,
        "expires_at": expires_at,
    }


def verify_email_otp(email: str, otp: str, current_user_id: str | None = None) -> dict[str, Any]:
    normalized_email = normalize_email(email)
    otp_value = str(otp or "").strip()
    if not otp_value:
        raise AuthError("Missing OTP code", status_code=400)

    now = _now()
    auth_identities, auth_otps, _, users = _collections()
    record = auth_otps.find_one({"email": normalized_email, "status": "pending"}, sort=[("created_at", -1)])
    if not record:
        raise AuthError("No active OTP code for this email", status_code=400)

    if int(record.get("expires_at", 0) or 0) <= now:
        auth_otps.update_one({"_id": record["_id"]}, {"$set": {"status": "expired", "updated_at": now}})
        raise AuthError("OTP code expired", status_code=400)

    provided_hash = _hash_token(f"{normalized_email}:{otp_value}")
    if provided_hash != str(record.get("otp_hash") or ""):
        attempts = int(record.get("attempts", 0) or 0) + 1
        next_status = "failed" if attempts >= MAX_OTP_ATTEMPTS else "pending"
        auth_otps.update_one(
            {"_id": record["_id"]},
            {"$set": {"attempts": attempts, "status": next_status, "updated_at": now}},
        )
        raise AuthError("Invalid OTP code", status_code=400)

    auth_otps.update_one({"_id": record["_id"]}, {"$set": {"status": "used", "updated_at": now, "used_at": now}})

    user_id = _resolve_canonical_user_id(normalized_email, current_user_id)
    users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "verified_email": normalized_email,
                "last_login_at": _utcnow(),
                "last_active_at": _utcnow(),
            }
        },
        upsert=True,
    )
    auth_identities.update_one(
        {"email": normalized_email},
        {"$set": {"user_id": user_id, "last_login_at": _utcnow()}},
        upsert=True,
    )
    session = _create_auth_session(user_id, normalized_email)
    return {
        "status": "authenticated",
        "user_id": user_id,
        "email": normalized_email,
        "auth_token": session["token"],
        "expires_at": session["expires_at"],
    }


def get_auth_session_from_header(authorization: str | None) -> dict[str, Any] | None:
    header = str(authorization or "").strip()
    if not header:
        return None

    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("Invalid authorization header", status_code=401)

    now = _now()
    _, _, auth_sessions, _ = _collections()
    session = auth_sessions.find_one(
        {
            "token_hash": _hash_token(token.strip()),
            "status": "active",
            "expires_at": {"$gt": now},
        },
        {"_id": 0, "user_id": 1, "email": 1, "expires_at": 1},
    )
    if not session:
        raise AuthError("Invalid or expired auth session", status_code=401)
    return session


def resolve_request_user_id(explicit_user_id: str | None, authorization: str | None) -> str:
    session = get_auth_session_from_header(authorization)
    if session:
        authorized_user_id = str(session.get("user_id") or "").strip()
        payload_user_id = str(explicit_user_id or "").strip()
        if payload_user_id and payload_user_id != authorized_user_id:
            raise AuthError("Authenticated user does not match requested user_id", status_code=403)
        return authorized_user_id

    if AUTH_REQUIRE_WEB_API:
        raise AuthError("Authentication required", status_code=401)

    fallback_user_id = str(explicit_user_id or "").strip()
    if not fallback_user_id:
        raise AuthError("Missing user_id", status_code=400)
    return fallback_user_id


def revoke_auth_session(authorization: str | None) -> None:
    header = str(authorization or "").strip()
    if not header:
        raise AuthError("Missing authorization header", status_code=401)

    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthError("Invalid authorization header", status_code=401)

    _, _, auth_sessions, _ = _collections()
    result = auth_sessions.update_one(
        {"token_hash": _hash_token(token.strip()), "status": "active"},
        {"$set": {"status": "revoked", "updated_at": _now()}},
        upsert=False,
    )
    if result.matched_count != 1:
        raise AuthError("Invalid or expired auth session", status_code=401)
