import json
import os
import tempfile

from openai import OpenAI
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from backend.handlers.interview_handler import (
    end_session,
    get_session,
    handle_next_question,
    set_pending_answer,
    start_interview,
)
from backend.handlers.payment_handler import POLICY_URL, create_payment_after_consent
from backend.services.llm_engine import generate_response
from backend.services.parser import process_documents
from backend.utils.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def map_decision(score: float):
    if score >= 8.5:
        return "Hire"
    elif score >= 7:
        return "Lean Hire"
    elif score >= 5:
        return "Borderline"
    else:
        return "Reject"


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


def build_policy_keyboard(plan_type):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("View Policy", url=POLICY_URL)],
            [InlineKeyboardButton("Buy 1 Session - Rs 99", callback_data="accept_policy:session")],
            [InlineKeyboardButton("Upgrade to Premium - Rs 499", callback_data="accept_policy:subscription")],
        ]
    )


async def send_policy_gate(message, plan_type):
    await message.reply_text(
        "Upgrade to Premium for your prep.\n\nBefore payment, you must accept our policy (no refunds).",
        reply_markup=build_policy_keyboard(plan_type),
    )


def begin_payment_wait(context, phase):
    context.user_data["awaiting_payment"] = True
    context.user_data["payment_context"] = phase


def clear_payment_wait(context):
    context.user_data.pop("awaiting_payment", None)
    context.user_data.pop("payment_context", None)
    context.user_data.pop("policy_accepted", None)
    context.user_data.pop("pending_payment_plan", None)


async def handle_awaiting_payment(message, context):
    payment_context = context.user_data.get("payment_context", "start")

    if payment_context == "continue":
        await message.reply_text(
            "Your payment link has already been shared.\n\n"
            "After successful payment, start a fresh session with /start."
        )
        return

    await message.reply_text(
        "Your payment link has already been shared.\n\n"
        "After successful payment, send /start to begin a new interview."
    )


async def handle_policy_accept(update, context):
    query = update.callback_query
    user_id = str(query.from_user.id)
    plan_type = query.data.split(":", 1)[1]

    context.user_data["policy_accepted"] = True
    context.user_data["pending_payment_plan"] = plan_type
    context.user_data["awaiting_payment"] = True

    payment_result = create_payment_after_consent(
        user_id,
        plan_type,
        context.user_data.get("policy_accepted", False),
    )

    await query.answer("Policy accepted")
    await query.edit_message_text(
        "Policy accepted.\n\n"
        f"{'Upgrade to Premium for your prep' if plan_type == 'subscription' else 'Buy 1 extra session'}\n\n"
        f"Complete payment here: {payment_result['payment_link']}"
    )


async def interview(update, context):
    message = update.message
    user_id = str(message.from_user.id)
    text = message.text
    document = message.document

    state = context.user_data.get("state")

    if state == "AWAITING_PAYMENT" or context.user_data.get("awaiting_payment"):
        await handle_awaiting_payment(message, context)
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

        previous_resume_path = context.user_data.get("resume_path")
        cleanup_temp_file(previous_resume_path)

        context.user_data["resume_path"] = await download_pdf(document)
        context.user_data["state"] = "ASK_JD"
        await message.reply_text("Step 3: Upload the JD as a PDF document.")
        return

    if state == "ASK_JD":
        if not document or document.mime_type != "application/pdf":
            await message.reply_text("Step 3 requires a PDF. Upload the JD PDF.")
            return

        previous_jd_path = context.user_data.get("jd_path")
        cleanup_temp_file(previous_jd_path)
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

        if start_result["status"] == "policy_required":
            cleanup_temp_file(context.user_data.pop("resume_path", None))
            cleanup_temp_file(context.user_data.pop("jd_path", None))
            context.user_data["state"] = "AWAITING_PAYMENT"
            begin_payment_wait(context, "start")
            await send_policy_gate(message, start_result["plan"])
            return

        if start_result["status"] in {"blocked", "payment_required"}:
            cleanup_temp_file(context.user_data.pop("resume_path", None))
            cleanup_temp_file(context.user_data.pop("jd_path", None))
            await message.reply_text(
                f"Limit reached.\n\nBuy 1 session here: {start_result['payment_link']}"
            )
            return

        if start_result["status"] != "started":
            cleanup_temp_file(context.user_data.pop("resume_path", None))
            cleanup_temp_file(context.user_data.pop("jd_path", None))
            await message.reply_text("Unable to start interview.")
            return

        context.user_data["state"] = "IN_INTERVIEW"

        await message.reply_text(
            "Interview started.\n\nTell me about yourself."
        )
        return

    session = get_session(user_id)

    if not session:
        await message.reply_text("Type /start to begin.")
        return

    if not text:
        await message.reply_text("Reply with text to continue the interview.")
        return

    if not set_pending_answer(user_id, text):
        await message.reply_text("Type /start to begin.")
        return

    handler_result = handle_next_question(user_id, generate_response)

    if handler_result["status"] == "policy_required":
        end_session(user_id)
        context.user_data["state"] = "AWAITING_PAYMENT"
        begin_payment_wait(context, "continue")
        await send_policy_gate(message, handler_result["plan"])
        return

    if handler_result["status"] in {"blocked", "payment_required"}:
        await message.reply_text(
            f"Limit reached.\n\nBuy 1 session here: {handler_result['payment_link']}"
        )
        return

    if handler_result["status"] != "ok":
        await message.reply_text("Type /start to begin.")
        return

    result = handler_result["data"]
    session = get_session(user_id)

    scores = session["scores"]

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
                {"role": "user", "content": evaluation_prompt}
            ]
        )

        try:
            final = json.loads(response.choices[0].message.content)
        except:
            final = {
                "reason": "Fundamental mismatch",
                "better_roles": ["Operations Analyst", "Support Analyst"],
                "action": "Build core skills"
            }

        end_session(user_id)
        context.user_data["state"] = None
        clear_payment_wait(context)
        context.user_data.pop("resume_path", None)
        context.user_data.pop("jd_path", None)

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

    if session["question_count"] >= 5:
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
                {"role": "user", "content": evaluation_prompt}
            ]
        )

        try:
            final = json.loads(response.choices[0].message.content)
        except:
            final = {
                "strengths": "Good base",
                "weaknesses": "Lacks depth",
                "action": "Improve structured answers"
            }

        end_session(user_id)
        context.user_data["state"] = None
        clear_payment_wait(context)
        context.user_data.pop("resume_path", None)
        context.user_data.pop("jd_path", None)

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
