from __future__ import annotations

import secrets
import string
import time

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from backend.services.db import account_links
from backend.user_store import get_user

LINK_CODE_ALPHABET = string.ascii_uppercase + string.digits
LINK_CODE_LENGTH = 8
LINK_CODE_TTL_SECONDS = 600
MAX_CODE_GENERATION_ATTEMPTS = 10


def _normalize_code(code: str) -> str:
    return "".join(character for character in str(code or "").upper() if character.isalnum())


def _generate_code() -> str:
    return "".join(secrets.choice(LINK_CODE_ALPHABET) for _ in range(LINK_CODE_LENGTH))


def create_link_code(user_id: str) -> dict[str, int | str]:
    owner_user_id = str(user_id).strip()
    if not owner_user_id:
        raise ValueError("Missing user_id")

    get_user(owner_user_id)

    now = int(time.time())
    expires_at = now + LINK_CODE_TTL_SECONDS

    account_links.update_many(
        {"owner_user_id": owner_user_id, "status": "pending"},
        {
            "$set": {
                "status": "replaced",
                "updated_at": now,
            }
        },
    )

    for _ in range(MAX_CODE_GENERATION_ATTEMPTS):
        code = _generate_code()
        try:
            account_links.insert_one(
                {
                    "code": code,
                    "owner_user_id": owner_user_id,
                    "status": "pending",
                    "created_at": now,
                    "updated_at": now,
                    "expires_at": expires_at,
                }
            )
            return {
                "code": code,
                "expires_at": expires_at,
                "expires_in_seconds": LINK_CODE_TTL_SECONDS,
            }
        except DuplicateKeyError:
            continue

    raise RuntimeError("Unable to generate a unique account link code")


def consume_link_code(user_id: str, code: str) -> str:
    device_user_id = str(user_id).strip()
    normalized_code = _normalize_code(code)
    if not device_user_id:
        raise ValueError("Missing user_id")
    if not normalized_code:
        raise ValueError("Missing code")

    now = int(time.time())
    get_user(device_user_id)

    link = account_links.find_one_and_update(
        {
            "code": normalized_code,
            "status": "pending",
            "expires_at": {"$gt": now},
        },
        {
            "$set": {
                "status": "used",
                "consumed_by_user_id": device_user_id,
                "used_at": now,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.BEFORE,
    )

    if link is None:
        existing = account_links.find_one({"code": normalized_code}, {"status": 1, "expires_at": 1, "_id": 0}) or {}
        if existing and int(existing.get("expires_at", 0) or 0) <= now:
            account_links.update_one(
                {"code": normalized_code},
                {"$set": {"status": "expired", "updated_at": now}},
            )
            raise ValueError("Link code expired")
        raise ValueError("Invalid link code")

    owner_user_id = str(link.get("owner_user_id") or "").strip()
    if not owner_user_id:
        raise RuntimeError("Link code is missing owner account information")

    get_user(owner_user_id)

    account_links.update_many(
        {"owner_user_id": owner_user_id, "status": "pending"},
        {"$set": {"status": "replaced", "updated_at": now}},
    )

    return owner_user_id
