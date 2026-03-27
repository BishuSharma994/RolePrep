import json
from openai import OpenAI
from backend.config import OPENAI_API_KEY
from backend.utils.prompts import SYSTEM_PROMPT

client = OpenAI(api_key=OPENAI_API_KEY)


def normalize_score(raw_score, session):
    """
    Expands score distribution to avoid 8–9 compression
    while preserving relative ordering.
    """
    scores = session.get("scores", []) if session else []

    if not scores:
        return raw_score

    avg = sum(scores) / len(scores)

    # Expansion logic
    if raw_score >= 9:
        return min(10, raw_score + 0.5)  # push excellence upward

    if raw_score >= 8:
        if avg >= 8:
            return min(10, raw_score + 0.3)
        return raw_score

    if raw_score >= 7:
        if avg < 7:
            return raw_score - 0.3  # penalize inconsistency
        return raw_score

    return raw_score


def generate_response(role, jd_text, user_input, session=None):
    history = session.get("history", [])[-5:] if session else []
    scores = session.get("scores", []) if session else []

    difficulty = "normal"
    if scores:
        avg = sum(scores) / len(scores)
        if avg >= 9:
            difficulty = "bar_raiser"
        elif avg >= 8.5:
            difficulty = "defense"
        elif avg >= 8:
            difficulty = "tradeoff"
        elif avg >= 7:
            difficulty = "hard"
        elif avg <= 4:
            difficulty = "pressure"

    user_prompt = f"""
Role: {role}

Job Description:
{jd_text}

Previous Answers:
{history}

Difficulty: {difficulty}

ANALYZE:

1. JD alignment
2. Metrics present
3. Trade-offs present
4. Reasoning depth
5. Consistency across answers

CLASSIFY INTO ONE:
- CONTRADICTION
- REPETITION
- SHALLOW_EXPLANATION
- STRONG

IMPORTANT:
- Only mark contradiction if clearly conflicting
- Prefer shallow over false contradiction

ACTIONS:

CONTRADICTION → challenge inconsistency  
REPETITION → force new example  
SHALLOW → deepen reasoning  
STRONG → challenge assumptions / scale / trade-offs  

Candidate Answer:
{user_input}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
    )

    content = response.choices[0].message.content

    try:
        parsed = json.loads(content)
    except:
        return {
            "score": 6,
            "feedback": "Response lacks depth and measurable reasoning.",
            "next_question": "Explain your decision with trade-offs and measurable impact."
        }

    raw_score = parsed.get("score", 6)

    # Apply normalization (key fix)
    final_score = round(normalize_score(raw_score, session), 1)

    return {
        "score": final_score,
        "feedback": parsed.get("feedback", ""),
        "next_question": parsed.get("next_question", "")
    }