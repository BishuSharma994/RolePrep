from __future__ import annotations

import re

_ACTION_VERBS = (
    "Built",
    "Designed",
    "Implemented",
    "Led",
    "Optimized",
    "Automated",
    "Delivered",
    "Improved",
    "Scaled",
    "Created",
)
_METRIC_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|x|ms|s|sec|seconds?|minutes?|hours?|days?|users?|requests?|records?|tickets?)\b", re.IGNORECASE)


def _normalize_line(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" -")
    return cleaned.rstrip(".")


def _starts_with_action_verb(text: str) -> bool:
    first_word = str(text or "").split(" ", 1)[0].capitalize() if text else ""
    return first_word in _ACTION_VERBS


def generate_bullet(text: str, jd_keywords: list) -> str:
    base_text = _normalize_line(text)
    if not base_text:
        base_text = "Improved a core workflow"

    if not _starts_with_action_verb(base_text):
        base_text = f"Built {base_text[:1].lower() + base_text[1:]}" if base_text else "Built a relevant solution"

    lowered = base_text.lower()
    aligned_keywords = [keyword for keyword in jd_keywords if keyword and keyword.lower() not in lowered][:2]
    if aligned_keywords:
        base_text = f"{base_text} aligned to {', '.join(aligned_keywords)}"

    if not _METRIC_PATTERN.search(base_text):
        base_text = f"{base_text}, improving [X metric] by [Y%]"

    return f"{base_text}."
