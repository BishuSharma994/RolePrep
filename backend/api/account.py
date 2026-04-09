from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()


class LinkCodeCreateRequest(BaseModel):
    user_id: str = Field(..., min_length=1)


class LinkCodeConsumeRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    code: str = Field(..., min_length=1)


def _create_link_code(user_id: str):
    from backend.account_link_store import create_link_code

    return create_link_code(user_id)


def _consume_link_code(user_id: str, code: str):
    from backend.account_link_store import consume_link_code

    return consume_link_code(user_id, code)


@router.post("/account/link-code")
async def create_account_link_code(payload: LinkCodeCreateRequest):
    user_id = str(payload.user_id).strip()

    try:
        result = _create_link_code(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create link code",
        ) from exc

    return {
        "status": "ready",
        "code": str(result["code"]),
        "expires_at": int(result["expires_at"]),
        "expires_in_seconds": int(result["expires_in_seconds"]),
    }


@router.post("/account/link")
async def link_account(payload: LinkCodeConsumeRequest):
    user_id = str(payload.user_id).strip()
    code = str(payload.code).strip()

    try:
        linked_user_id = _consume_link_code(user_id, code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to link account",
        ) from exc

    return {
        "status": "linked",
        "user_id": str(linked_user_id),
    }
