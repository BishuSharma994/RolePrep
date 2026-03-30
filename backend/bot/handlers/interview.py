import json
import os
import tempfile

from openai import OpenAI

from backend.handlers.interview_handler import (
    end_session,
    get_session,
    handle_next_question,
    run_interview_engine,
    set_pending_answer,
    start_interview,
)
from backend.handlers.payment_handler import handle_payment_request
from backend.handlers.plan_handler import get_plan
from backend.rate_limit import allow_request
from backend.services.parser import process_documents
from backend.services.plan_manager import get_current_access_mode, get_session_credits, is_subscription_active
from backend.utils.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

FREE_QUESTION_LIMIT = 5
PAID_QUESTION_LIMIT = 10


def map_decision(score: float):
    if score >= 8.5:
        return "Hire"
    if score >= 7:
        return "Lean Hire"
    if score >= 5:
        return "Borderline"
    return "Reject"


def current_question_limit(user_id: str) -> int:
    if get_current_access_mode(user_id) == "free":
        return FREE_QUESTION_LIMIT
    return PAID_QUESTION_LIMIT


def has_selected_plan_access(user_id: str, plan_type: str) -> bool:
    if plan_type == "premium":
        return is_subscription_active(user_id)
    if plan_type in {"session", "session_10", "session_29"}:
        return get_session_credits(user_id) > 0
    return True


async def download_pdf(document):
    suffix = os.path.splitext(document.file_name or "")[1] or ".pdf"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = temp_file.name

    telegram_file = await document.get_file()
    await telegram_file.download_to_drive(custom_path=temp_path)
    return temp_path


def cleanup_temp_file(file_path):
    if file_path and os.path.exists(file_path):
        os.remove(file_path)


def cleanup_context_files(context):
    cleanup_temp_file(context.user_data.pop("resume_path", None))
    cleanup_temp_file(context.user_data.pop("jd_path", None))


async def send_payment_required(message, user_id: str, selected_plan: str | None):
    plan_type = selected_plan if selected_plan in {"session_10", "session_29", "premium"} else "session_10"
    payment_result = handle_payment_request(user_id, plan_type)
    if plan_type == "premium":
        label = "Premium"
    elif plan_type == "session_29":
        label = "5 Session Pack"
    else:
        label = "1 Session Pack"
    await message.reply_text(
        f"{label} required to continue.\n\n"
        f"Complete payment here: {payment_result['payment_link']}\n\n"
        "After successful payment confirmation, send /start and select your plan again."
    )


async def interview(update, context):
    message = update.message
    user_id = str(message.from_user.id)
    if not allow_request(user_id):
        await message.reply_text("Too many requests. Please slow down.")
        return

    text = message.text
    document = message.document

    selected_plan = get_plan(user_id) or context.user_data.get("selected_plan")
    state = context.user_data.get("state")

    if not selected_plan:
        await message.reply_text("Use /start and select a plan first.")
        return

    context.user_data["selected_plan"] = selected_plan

    if state == "AWAITING_PAYMENT":
        await send_payment_required(message, user_id, selected_plan)
        return

    if selected_plan != "free" and not has_selected_plan_access(user_id, selected_plan):
        context.user_data["state"] = "AWAITING_PAYMENT"
        await send_payment_required(message, user_id, selected_plan)
        return

    if state == "ASK_ROLE":
        if not text:
            await message.reply_text("Step 1 requires text. Enter the role you are applying for.")
            return

        context.user_data["role"] = text
        context.user_data["state"] = "ASK_RESUME"
        await message.reply_text("Step 2: Upload your resume as a PDF document.")
        return

    if state == "ASK_RESUME":
        if not document or document.mime_type != "application/pdf":
            await message.reply_text("Step 2 requires a PDF. Upload your resume PDF.")
            return

        cleanup_temp_file(context.user_data.get("resume_path"))
        context.user_data["resume_path"] = await download_pdf(document)
        context.user_data["state"] = "ASK_JD"
        await message.reply_text("Step 3: Upload the JD as a PDF document.")
        return

    if state == "ASK_JD":
        if not document or document.mime_type != "application/pdf":
            await message.reply_text("Step 3 requires a PDF. Upload the JD PDF.")
            return

        cleanup_temp_file(context.user_data.get("jd_path"))
        jd_path = await download_pdf(document)
        context.user_data["jd_path"] = jd_path

        try:
            parsed_data = process_documents(
                context.user_data["resume_path"],
                jd_path,
            )
        except Exception:
            cleanup_temp_file(jd_path)
            context.user_data.pop("jd_path", None)
            await message.reply_text("Unable to parse the resume/JD PDFs. Please upload valid PDF files.")
            return

        jd_text = parsed_data.get("raw", {}).get("jd_text", "").strip()
        if not jd_text:
            cleanup_temp_file(jd_path)
            context.user_data.pop("jd_path", None)
            await message.reply_text("JD PDF parsing returned empty text. Please upload a readable JD PDF.")
            return

        start_result = start_interview(
            user_id,
            role=context.user_data["role"],
            jd_text=jd_text,
            parser_data=parsed_data,
            resume_path=context.user_data["resume_path"],
            jd_path=jd_path,
        )

        if start_result["status"] == "blocked":
            cleanup_context_files(context)
            context.user_data["state"] = "AWAITING_PAYMENT"
            await send_payment_required(message, user_id, selected_plan)
            return

        if start_result["status"] != "started":
            cleanup_context_files(context)
            await message.reply_text("Unable to start interview.")
            return

        context.user_data["state"] = "IN_INTERVIEW"
        await message.reply_text("Interview started.\n\nTell me about yourself.")
        return

    session = get_session(user_id)

    if not session:
        await message.reply_text("Use /start and select a plan first.")
        return

    if not text:
        await message.reply_text("Reply with text to continue the interview.")
        return

    if not set_pending_answer(user_id, text):
        await message.reply_text("Use /start and select a plan first.")
        return

    handler_result = handle_next_question(user_id, run_interview_engine)

    if handler_result["status"] == "blocked":
        end_session(user_id)
        context.user_data["state"] = "AWAITING_PAYMENT"
        await send_payment_required(message, user_id, selected_plan)
        return

    if handler_result["status"] != "ok":
        await message.reply_text("Use /start and select a plan first.")
        return

    result = handler_result["data"]
    session = get_session(user_id)
    scores = session["scores"]
    question_limit = current_question_limit(user_id)

    if len(scores) >= 2 and scores[-1] <= 2 and scores[-2] <= 2:
        avg_score = round(sum(scores) / len(scores), 1)
        decision = map_decision(avg_score)

        evaluation_prompt = f"""
You are a strict hiring manager.

Candidate is not suitable.

Role:
{session['role']}

JD:
{session['jd_text']}

Answers:
{session['history']}

Scores:
{scores}

Provide reason, better roles, and improvement plan.

OUTPUT JSON:
{{
  "reason": "...",
  "better_roles": ["role1", "role2"],
  "action": "..."
}}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Strict interviewer"},
                {"role": "user", "content": evaluation_prompt},
            ],
        )

        try:
            final = json.loads(response.choices[0].message.content)
        except Exception:
            final = {
                "reason": "Fundamental mismatch",
                "better_roles": ["Operations Analyst", "Support Analyst"],
                "action": "Build core skills",
            }

        end_session(user_id)
        context.user_data["state"] = None
        cleanup_context_files(context)

        await message.reply_text(
            f"""Final Evaluation (Early Termination):

Score: {avg_score}/10
Decision: {decision}

Reason:
{final['reason']}

Better Role Fit:
- {chr(10).join(final['better_roles'])}

Action:
{final['action']}
"""
        )
        return

    if session["question_count"] >= question_limit:
        avg_score = round(sum(scores) / len(scores), 1)
        decision = map_decision(avg_score)

        evaluation_prompt = f"""
You are a strict hiring manager.

Evaluate candidate.

Role:
{session['role']}

JD:
{session['jd_text']}

Answers:
{session['history']}

Scores:
{scores}

Provide strengths, weaknesses, action.

OUTPUT JSON:
{{
  "strengths": "...",
  "weaknesses": "...",
  "action": "..."
}}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Strict interviewer"},
                {"role": "user", "content": evaluation_prompt},
            ],
        )

        try:
            final = json.loads(response.choices[0].message.content)
        except Exception:
            final = {
                "strengths": "Good base",
                "weaknesses": "Lacks depth",
                "action": "Improve structured answers",
            }

        end_session(user_id)
        context.user_data["state"] = None
        cleanup_context_files(context)

        await message.reply_text(
            f"""Final Evaluation:

Score: {avg_score}/10
Decision: {decision}

Strengths:
{final['strengths']}

Weaknesses:
{final['weaknesses']}

Action:
{final['action']}
"""
        )
        return

    await message.reply_text(
        f"Score: {result['score']}\n{result['feedback']}\n\nNext: {result['next_question']}"
    )
