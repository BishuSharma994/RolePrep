from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.handlers.payment_handler import handle_payment_request

router = APIRouter()

SUPPORTED_PLAN_TYPES = {"session_10", "session_29", "premium"}


class PaymentLinkRequest(BaseModel):
    user_id: str | None = None
    plan_type: str = Field(..., min_length=1)


def _resolve_request_user_id(user_id: str | None, authorization: str | None) -> str:
    from backend.auth_service import AuthError, resolve_request_user_id

    try:
        return resolve_request_user_id(user_id, authorization)
    except AuthError:
        raise


@router.post("/payments/link")
async def create_payment_link(payload: PaymentLinkRequest, request: Request):
    from backend.auth_service import AuthError

    try:
        user_id = _resolve_request_user_id(payload.user_id, request.headers.get("authorization"))
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    plan_type = str(payload.plan_type).strip()

    if plan_type not in SUPPORTED_PLAN_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid plan_type",
        )

    try:
        response = handle_payment_request(user_id=user_id, plan_type=plan_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment link",
        ) from exc

    payment_link = str(response.get("payment_link") or "").strip()
    if not payment_link:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment link",
        )

    return {
        "status": str(response.get("status") or "pending"),
        "payment_link": payment_link,
    }
