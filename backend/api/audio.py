from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from backend.services.answer_analysis_types import AnswerAnalysisRequest
from backend.services.answer_failure_engine import analyze_answer
from backend.services.stt_service import STTService
from backend.services.voice_signal_extractor import extract_voice_signals

router = APIRouter()
TMP_AUDIO_DIR = Path("tmp_audio")


def _safe_suffix(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix else ".wav"


def _record_answer_analysis(user_id: str, answer_text: str, analysis: dict) -> bool:
    from backend.handlers.interview_handler import record_answer_analysis

    return record_answer_analysis(user_id, answer_text, analysis)


def _get_session(user_id: str):
    from backend.handlers.interview_handler import get_session

    return get_session(user_id)


def _resolve_request_user_id(user_id: str | None, authorization: str | None) -> str:
    from backend.auth_service import AuthError, resolve_request_user_id

    try:
        return resolve_request_user_id(user_id, authorization)
    except AuthError:
        raise


@router.post("/analyze-audio")
async def analyze_audio(
    request: Request,
    file: UploadFile = File(...),
    role: str = Form(""),
    jd_text: str = Form(""),
    current_question: str = Form(""),
    user_id: str = Form(""),
):
    TMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = TMP_AUDIO_DIR / f"{uuid.uuid4().hex}{_safe_suffix(file.filename)}"

    try:
        with temp_path.open("wb") as output_stream:
            shutil.copyfileobj(file.file, output_stream)

        stt_result = STTService().transcribe(temp_path)
        transcript = str(stt_result.get("transcript") or "")
        segments = list(stt_result.get("segments") or [])
        voice_analysis = extract_voice_signals(segments, transcript)
        analysis_request = AnswerAnalysisRequest(
            role=str(role or ""),
            jd_text=str(jd_text or ""),
            current_question=str(current_question or ""),
            answer_text=transcript,
            parser_data={"voice_signals": voice_analysis},
        )
        analysis = analyze_answer(analysis_request)
        content_analysis = analysis.to_dict()
        from backend.auth_service import AUTH_REQUIRE_WEB_API, AuthError

        normalized_user_id = ""
        has_auth_header = bool(str(request.headers.get("authorization") or "").strip())
        if str(user_id or "").strip() or has_auth_header or AUTH_REQUIRE_WEB_API:
            try:
                normalized_user_id = _resolve_request_user_id(user_id, request.headers.get("authorization"))
            except AuthError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

        session_updated = False
        session_payload = None

        if normalized_user_id:
            session_updated = _record_answer_analysis(normalized_user_id, transcript, content_analysis)
            if session_updated:
                session = _get_session(normalized_user_id) or {}
                session_payload = {
                    "user_id": normalized_user_id,
                    "session_id": session.get("session_id"),
                    "current_question": session.get("current_question"),
                    "current_stage": session.get("current_stage"),
                    "question_count": int(session.get("question_count", 0) or 0),
                    "scores": list(session.get("scores", [])),
                    "latest_answer_analysis": session.get("latest_answer_analysis"),
                }

        return {
            "transcript": transcript,
            "segments": segments,
            "analysis": {
                **content_analysis,
                "content": content_analysis,
                "voice": voice_analysis,
            },
            "audio_metrics": {
                "pause_count": int(stt_result.get("pause_count", 0) or 0),
                "avg_pause": float(stt_result.get("avg_pause", 0.0) or 0.0),
                "pauses": stt_result.get("pauses", []),
            },
            "session_updated": session_updated,
            "session": session_payload,
        }
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - error path is straightforward
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        try:
            file.file.close()
        except Exception:
            pass
        if temp_path.exists():
            temp_path.unlink()
