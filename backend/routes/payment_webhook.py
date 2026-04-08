from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from backend.payment_store import (
    get_payment_record,
    is_payment_processed,
    process_captured_payment,
    process_failed_payment,
)
from backend.services.activity import update_last_payment_at, update_user_last_active
from backend.services.payment import verify_webhook_signature
from backend.utils.logger import log_event
from backend.webhook_store import mark_event_processed, record_webhook_event, update_webhook_event

router = APIRouter()

_SUPPORTED_EVENTS = {"payment.captured", "payment.failed"}


def extract_event_id(payload: dict[str, Any]) -> str | None:
    event_id = payload.get("id")
    if event_id is None:
        return None
    return str(event_id)


def _payment_entity(payload: dict[str, Any]) -> dict[str, Any]:
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    return payment if isinstance(payment, dict) else {}


def _payment_metadata(payment: dict[str, Any]) -> dict[str, Any]:
    notes = payment.get("notes", {}) or {}
    if not isinstance(notes, dict):
        notes = {}
    return {
        "payment_id": str(payment.get("id") or ""),
        "payment_status": str(payment.get("status") or ""),
        "user_id": str(notes.get("user_id") or ""),
        "plan": str(notes.get("plan") or ""),
        "email": str(payment.get("email") or ""),
        "contact": str(payment.get("contact") or ""),
        "notes": notes,
    }


def _resolve_payment_context(payment_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(metadata)
    if payment_id and (not resolved.get("user_id") or not resolved.get("plan")):
        payment_record = get_payment_record(payment_id) or {}
        resolved["user_id"] = str(resolved.get("user_id") or payment_record.get("user_id") or "")
        resolved["plan"] = str(
            resolved.get("plan")
            or payment_record.get("raw_plan")
            or payment_record.get("plan")
            or ""
        )
    return resolved


def _duplicate_response(event_id: str, event: str, payment_id: str, user_id: str | None, plan: str | None):
    return {
        "status": "ignored",
        "reason": "duplicate",
        "event_id": event_id,
        "event": event,
        "payment_id": payment_id,
        "user_id": user_id,
        "plan": plan,
    }


@router.post("/webhook/razorpay")
async def payment_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature")

    if not signature:
        log_event("webhook_signature_missing", {"signature_present": False})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Razorpay signature")

    try:
        is_valid_signature = verify_webhook_signature(raw_body, signature)
    except Exception as exc:
        log_event(
            "webhook_signature_verification_failed",
            {
                "signature_present": True,
                "error": repr(exc),
            },
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook verification failed") from exc

    if not is_valid_signature:
        log_event("webhook_signature_invalid", {"signature_present": True})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Razorpay signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        log_event("webhook_payload_invalid", {"error": repr(exc)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook payload") from exc

    if not isinstance(payload, dict):
        log_event("webhook_payload_invalid", {"error": "payload_not_object"})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook payload must be a JSON object")

    event_id = extract_event_id(payload)
    if not event_id:
        log_event("webhook_event_id_missing", {"payload": payload})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing webhook event id")

    event = str(payload.get("event") or "")
    record_status = record_webhook_event(event_id, event, payload)
    if record_status == "duplicate":
        log_event("webhook_duplicate", {"event_id": event_id, "event": event})
        return _duplicate_response(event_id, event, "", None, None)

    if event not in _SUPPORTED_EVENTS:
        update_webhook_event(event_id, "ignored", error="unsupported_event")
        log_event("webhook_ignored", {"event_id": event_id, "event": event})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported webhook event: {event}")

    payment = _payment_entity(payload)
    metadata = _resolve_payment_context(
        str(payment.get("id") or ""),
        _payment_metadata(payment),
    )
    payment_id = metadata["payment_id"]
    payment_status = metadata["payment_status"]
    user_id = metadata["user_id"]
    plan = metadata["plan"]
    received_at = int(time.time())

    log_event(
        "webhook_received",
        {
            "event_id": event_id,
            "event": event,
            "payment_id": payment_id,
            "payment_status": payment_status,
            "user_id": user_id or None,
            "plan": plan or None,
            "received_at": received_at,
            "record_status": record_status,
        },
    )

    if not payment_id:
        update_webhook_event(event_id, "validation_failed", error="missing_payment_id")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing payment id")

    if event == "payment.captured":
        if payment_status != "captured" or not user_id or not plan:
            update_webhook_event(
                event_id,
                "validation_failed",
                payment_id=payment_id,
                payment_status=payment_status,
                user_id=user_id or None,
                plan=plan or None,
                error="invalid_captured_payment_payload",
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Captured payment webhook is missing required payment metadata",
            )

        update_user_last_active(user_id)

        if is_payment_processed(payment_id):
            update_webhook_event(
                event_id,
                "processed",
                payment_id=payment_id,
                user_id=user_id,
                plan=plan,
                reason="payment_already_processed",
            )
            log_event(
                "webhook_duplicate",
                {
                    "event_id": event_id,
                    "event": event,
                    "payment_id": payment_id,
                    "user_id": user_id,
                    "plan": plan,
                    "reason": "payment_already_processed",
                },
            )
            return _duplicate_response(event_id, event, payment_id, user_id, plan)

        try:
            processing_status = process_captured_payment(payment_id, user_id, plan, event_id)
        except Exception as exc:
            update_webhook_event(
                event_id,
                "failed",
                payment_id=payment_id,
                user_id=user_id,
                plan=plan,
                error=repr(exc),
            )
            log_event(
                "webhook_processing_failed",
                {
                    "event_id": event_id,
                    "event": event,
                    "payment_id": payment_id,
                    "user_id": user_id,
                    "plan": plan,
                    "error": repr(exc),
                },
            )
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process payment") from exc

        if processing_status != "processed":
            update_webhook_event(
                event_id,
                "failed",
                payment_id=payment_id,
                user_id=user_id,
                plan=plan,
                error=f"unexpected_processing_status:{processing_status}",
            )
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected payment processing status")

        update_last_payment_at(user_id)
        mark_event_processed(
            event_id,
            event_type=event,
            payment_id=payment_id,
            user_id=user_id,
            plan=plan,
            processed_event="payment.captured",
        )
        return {
            "status": "processed",
            "event_id": event_id,
            "event": event,
            "payment_id": payment_id,
            "user_id": user_id,
            "plan": plan,
        }

    failure_reason = (
        payment.get("error_description")
        or payment.get("description")
        or payload.get("description")
        or "payment.failed"
    )
    try:
        process_failed_payment(
            payment_id=payment_id,
            user_id=user_id or None,
            plan=plan or None,
            event_id=event_id,
            error_message=str(failure_reason),
        )
    except Exception as exc:
        update_webhook_event(
            event_id,
            "failed",
            payment_id=payment_id,
            user_id=user_id or None,
            plan=plan or None,
            error=repr(exc),
        )
        log_event(
            "webhook_processing_failed",
            {
                "event_id": event_id,
                "event": event,
                "payment_id": payment_id,
                "user_id": user_id or None,
                "plan": plan or None,
                "error": repr(exc),
            },
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to record failed payment") from exc

    mark_event_processed(
        event_id,
        event_type=event,
        payment_id=payment_id,
        user_id=user_id or None,
        plan=plan or None,
        processed_event="payment.failed",
        failure_reason=str(failure_reason),
    )
    return {
        "status": "processed",
        "event_id": event_id,
        "event": event,
        "payment_id": payment_id,
        "user_id": user_id or None,
        "plan": plan or None,
    }
