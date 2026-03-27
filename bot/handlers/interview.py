import json

from openai import OpenAI

from backend.config import OPENAI_API_KEY
from backend.handlers.interview_handler import (
    end_session,
    get_session,
    handle_next_question,
    set_pending_answer,
    start_interview,
)
from backend.services.llm_engine import generate_response

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


async def interview(update, context):
    user_id = str(update.message.from_user.id)
    text = update.message.text

    state = context.user_data.get("state")

    # Step 1: Role
    if state == "ASK_ROLE":
        context.user_data["role"] = text
        context.user_data["state"] = "ASK_JD"
        await update.message.reply_text("Step 2: Paste the Job Description (JD).")
        return

    # Step 2: JD
    if state == "ASK_JD":
        context.user_data["jd_text"] = text

        start_result = start_interview(
            user_id,
            role=context.user_data["role"],
            jd_text=context.user_data["jd_text"],
        )

        if start_result["status"] != "started":
            await update.message.reply_text("Daily free limit reached.")
            return

        context.user_data["state"] = "IN_INTERVIEW"

        await update.message.reply_text(
            "Interview started.\n\nTell me about yourself."
        )
        return

    # Interview Loop
    session = get_session(user_id)

    if not session:
        await update.message.reply_text("Type /start to begin.")
        return

    if not set_pending_answer(user_id, text):
        await update.message.reply_text("Type /start to begin.")
        return

    handler_result = handle_next_question(user_id, generate_response)

    if handler_result["status"] == "blocked":
        await update.message.reply_text("Session question limit reached.")
        return

    if handler_result["status"] != "ok":
        await update.message.reply_text("Type /start to begin.")
        return

    result = handler_result["data"]
    session = get_session(user_id)

    scores = session["scores"]

    # -------- EARLY TERMINATION --------
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

        await update.message.reply_text(
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

    # -------- NORMAL FINAL --------
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

        await update.message.reply_text(
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

    await update.message.reply_text(
        f"Score: {result['score']}\n{result['feedback']}\n\nNext: {result['next_question']}"
    )
