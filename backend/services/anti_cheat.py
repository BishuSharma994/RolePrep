import re
import time


_AI_STYLE_PHRASES = (
    "in conclusion",
    "furthermore",
    "it is important to note",
)

_WORD_PATTERN = re.compile(r"\b\w+\b")


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return _WORD_PATTERN.findall(text.lower())


def analyze_response(question_ts: float, answer: str) -> dict:
    response_time = None
    if isinstance(question_ts, (int, float)) and question_ts > 0:
        response_time = max(0.0, time.time() - float(question_ts))

    word_count = len(_tokenize(answer))
    normalized_answer = (answer or "").lower()

    too_fast = response_time is not None and response_time < 3 and word_count > 50
    too_long_fast = response_time is not None and response_time < 5 and word_count > 120
    structured_ai_style = any(phrase in normalized_answer for phrase in _AI_STYLE_PHRASES)

    return {
        "response_time": response_time,
        "word_count": word_count,
        "too_fast": too_fast,
        "too_long_fast": too_long_fast,
        "structured_ai_style": structured_ai_style,
    }


def generate_followup(flags: dict, answer: str) -> dict:
    _ = answer
    if flags.get("too_fast") or flags.get("structured_ai_style"):
        return {
            "type": "trap_rephrase",
            "question": "Explain your answer in your own words in 2 sentences",
        }

    return {
        "type": "normal",
        "question": "Why did you choose that approach?",
    }


def consistency_score(ans1: str, ans2: str) -> float:
    tokens1 = set(_tokenize(ans1))
    tokens2 = set(_tokenize(ans2))

    if not tokens1 and not tokens2:
        return 100.0
    if not tokens1 or not tokens2:
        return 0.0

    union = tokens1 | tokens2
    overlap = tokens1 & tokens2
    score = (len(overlap) / len(union)) * 100
    return round(score, 2)


def compute_final_score(clarity, depth, consistency):
    final_score = (float(clarity) * 0.3) + (float(depth) * 0.3) + (float(consistency) * 0.4)
    return round(final_score, 2)


def generate_feedback(flags, consistency):
    if flags.get("too_fast"):
        return "You answered very quickly. Try explaining in your own words."
    if float(consistency) < 40:
        return "Your follow-up answer was inconsistent. Focus on clarity."
    return "Good attempt. Add more personal experience."
