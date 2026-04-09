from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

router = APIRouter()


class ResumeGenerateRequest(BaseModel):
    user_id: str | None = None
    jd_text: str = Field(..., min_length=1)
    raw_text: str | None = None
    session_id: str | None = None

    @model_validator(mode="after")
    def validate_source(self):
        if not str(self.raw_text or "").strip() and not str(self.session_id or "").strip():
            raise ValueError("Provide raw_text or session_id")
        return self


class ResumeImproveRequest(BaseModel):
    user_id: str | None = None
    jd_text: str = Field(..., min_length=1)
    resume_json: dict[str, Any] | None = None
    raw_text: str | None = None
    session_id: str | None = None

    @model_validator(mode="after")
    def validate_source(self):
        if self.resume_json:
            return self
        if not str(self.raw_text or "").strip() and not str(self.session_id or "").strip():
            raise ValueError("Provide resume_json, raw_text, or session_id")
        return self


def _get_users_collection():
    from backend.services.db import users

    return users


def _get_resumes_collection():
    from backend.services.db import resumes

    return resumes


def _resolve_request_user_id(user_id: str | None, authorization: str | None) -> str:
    from backend.auth_service import AuthError, resolve_request_user_id

    try:
        return resolve_request_user_id(user_id, authorization)
    except AuthError:
        raise


def _parse_jd(jd_text: str) -> dict[str, Any]:
    from backend.services.jd_parser import parse_jd

    return parse_jd(jd_text)


def _generate_bullet(text: str, jd_keywords: list[str]) -> str:
    from backend.services.bullet_generator import generate_bullet

    return generate_bullet(text, jd_keywords)


def _build_resume(input_data: dict[str, Any], jd_data: dict[str, Any]) -> dict[str, Any]:
    from backend.services.resume_builder import build_resume

    return build_resume(input_data, jd_data)


def _generate_pdf(resume_json: dict[str, Any]) -> bytes:
    from backend.services.pdf_generator import generate_pdf

    return generate_pdf(resume_json)


def _parse_answer(text: str):
    from backend.services.answer_parser import parse_answer

    return parse_answer(text)


def _extract_signals(answer_text: str, sentences, jd_text: str, parser_data: dict[str, Any]):
    from backend.services.signal_extractor import extract_signals

    return extract_signals(
        answer_text=answer_text,
        sentences=sentences,
        current_question=str(parser_data.get("role") or ""),
        jd_text=jd_text,
        parser_data=parser_data,
    )


def _serialize_resume_document(document: dict[str, Any], include_pdf: bool = False) -> dict[str, Any]:
    payload = {
        "user_id": str(document.get("user_id") or ""),
        "jd_text": str(document.get("jd_text") or ""),
        "resume_json": document.get("resume_json") or {},
        "created_at": document.get("created_at"),
    }
    if include_pdf:
        pdf_bytes = _generate_pdf(payload["resume_json"])
        payload["pdf_base64"] = base64.b64encode(pdf_bytes).decode("ascii")
        payload["pdf_filename"] = f"roleprep_resume_{payload['user_id'] or 'draft'}.pdf"
        payload["content_type"] = "application/pdf"
    return payload


def _session_source(session_id: str) -> dict[str, Any]:
    document = _get_users_collection().find_one(
        {"session_id": str(session_id).strip()},
        {
            "_id": 0,
            "user_id": 1,
            "session_id": 1,
            "session_role": 1,
            "session_jd_text": 1,
            "session_history": 1,
            "latest_answer_analysis": 1,
        },
    )
    if not document:
        raise HTTPException(status_code=404, detail="Session not found")

    history = [str(item) for item in list(document.get("session_history") or []) if str(item or "").strip()]
    latest_answer_analysis = document.get("latest_answer_analysis") or {}
    latest_summary = str(latest_answer_analysis.get("feedback_summary") or "")
    role = str(document.get("session_role") or "")
    source_lines = history[:]
    if latest_summary:
        source_lines.append(latest_summary)
    if role:
        source_lines.append(role)

    return {
        "user_id": str(document.get("user_id") or ""),
        "raw_text": "\n".join(source_lines).strip(),
        "session_role": role,
        "session_jd_text": str(document.get("session_jd_text") or ""),
    }


def _normalize_resume_user_id(
    requested_user_id: str | None,
    authorization: str | None,
    fallback_user_id: str | None = None,
) -> str:
    from backend.auth_service import AUTH_REQUIRE_WEB_API, AuthError

    explicit_user_id = str(requested_user_id or fallback_user_id or "").strip()
    if explicit_user_id or AUTH_REQUIRE_WEB_API or str(authorization or "").strip():
        try:
            return _resolve_request_user_id(explicit_user_id or None, authorization)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    if not explicit_user_id:
        raise HTTPException(status_code=400, detail="Missing user_id")
    return explicit_user_id


def _resume_input_from_text(raw_text: str, jd_data: dict[str, Any]) -> dict[str, Any]:
    normalized_text = str(raw_text or "").strip()
    sentences, _ = _parse_answer(normalized_text)
    signals = _extract_signals(
        answer_text=normalized_text,
        sentences=sentences,
        jd_text=str(jd_data.get("normalized_text") or ""),
        parser_data={"jd": jd_data, "role": jd_data.get("role")},
    )

    source_sentences = [sentence.text for sentence in sentences if sentence.token_count >= 4]
    if not source_sentences and normalized_text:
        source_sentences = [normalized_text]

    bullets = [_generate_bullet(sentence, list(jd_data.get("keywords") or [])) for sentence in source_sentences[:8]]
    skills = list(jd_data.get("skills") or [])
    skills.extend(tool.tool for tool in list(signals.tools or []))
    return {
        "raw_text": normalized_text,
        "bullets": bullets,
        "skills": skills,
        "signals": signals.to_dict(),
    }


def _save_resume(user_id: str, jd_text: str, resume_json: dict[str, Any]) -> dict[str, Any]:
    document = {
        "user_id": str(user_id),
        "jd_text": str(jd_text),
        "resume_json": resume_json,
        "created_at": datetime.utcnow(),
    }
    _get_resumes_collection().insert_one(document)
    return document


def _build_response(document: dict[str, Any]) -> dict[str, Any]:
    pdf_bytes = _generate_pdf(document["resume_json"])
    return {
        "status": "generated",
        "user_id": str(document.get("user_id") or ""),
        "jd_text": str(document.get("jd_text") or ""),
        "resume_json": document.get("resume_json") or {},
        "created_at": document.get("created_at"),
        "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        "pdf_filename": f"roleprep_resume_{str(document.get('user_id') or 'draft')}.pdf",
        "content_type": "application/pdf",
    }


@router.post("/resume/generate")
async def generate_resume(payload: ResumeGenerateRequest, request: Request):
    session_source = _session_source(payload.session_id) if str(payload.session_id or "").strip() else {}
    jd_text = str(payload.jd_text).strip() or str(session_source.get("session_jd_text") or "").strip()
    if not jd_text:
        raise HTTPException(status_code=400, detail="Missing jd_text")

    user_id = _normalize_resume_user_id(
        requested_user_id=payload.user_id,
        authorization=request.headers.get("authorization"),
        fallback_user_id=session_source.get("user_id"),
    )
    raw_text = str(payload.raw_text or session_source.get("raw_text") or "").strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Missing raw_text source")

    jd_data = _parse_jd(jd_text)
    resume_input = _resume_input_from_text(raw_text, jd_data)
    resume_json = _build_resume(resume_input, jd_data)
    document = _save_resume(user_id=user_id, jd_text=jd_text, resume_json=resume_json)
    return _build_response(document)


@router.post("/resume/improve")
async def improve_resume(payload: ResumeImproveRequest, request: Request):
    session_source = _session_source(payload.session_id) if str(payload.session_id or "").strip() else {}
    jd_text = str(payload.jd_text).strip() or str(session_source.get("session_jd_text") or "").strip()
    if not jd_text:
        raise HTTPException(status_code=400, detail="Missing jd_text")

    user_id = _normalize_resume_user_id(
        requested_user_id=payload.user_id,
        authorization=request.headers.get("authorization"),
        fallback_user_id=session_source.get("user_id"),
    )
    jd_data = _parse_jd(jd_text)

    if payload.resume_json:
        experience = list(payload.resume_json.get("experience") or [])
        projects = list(payload.resume_json.get("projects") or [])
        improved_bullets: list[str] = []
        for section in (experience, projects):
            for item in section:
                for bullet in list(item.get("bullets") or []):
                    improved_bullets.append(_generate_bullet(str(bullet), list(jd_data.get("keywords") or [])))
        resume_input = {
            "bullets": improved_bullets,
            "skills": list(payload.resume_json.get("skills") or []),
        }
    else:
        raw_text = str(payload.raw_text or session_source.get("raw_text") or "").strip()
        if not raw_text:
            raise HTTPException(status_code=400, detail="Missing improve source")
        resume_input = _resume_input_from_text(raw_text, jd_data)

    resume_json = _build_resume(resume_input, jd_data)
    document = _save_resume(user_id=user_id, jd_text=jd_text, resume_json=resume_json)
    return _build_response(document)


@router.get("/resume/{user_id}")
async def get_resume(user_id: str, request: Request):
    resolved_user_id = _normalize_resume_user_id(
        requested_user_id=user_id,
        authorization=request.headers.get("authorization"),
    )
    document = _get_resumes_collection().find_one(
        {"user_id": resolved_user_id},
        sort=[("created_at", -1)],
    )
    if not document:
        raise HTTPException(status_code=404, detail="Resume not found")
    return _serialize_resume_document(document, include_pdf=True)
