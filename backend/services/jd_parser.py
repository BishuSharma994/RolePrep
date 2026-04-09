from __future__ import annotations

import re

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "have",
    "in",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
    "will",
    "you",
    "your",
}

_KNOWN_SKILLS = {
    "agile",
    "airflow",
    "aws",
    "azure",
    "ci/cd",
    "docker",
    "fastapi",
    "figma",
    "flask",
    "gcp",
    "git",
    "golang",
    "graphql",
    "java",
    "javascript",
    "jira",
    "kafka",
    "kubernetes",
    "linux",
    "mongodb",
    "mysql",
    "next.js",
    "node.js",
    "postgres",
    "postgresql",
    "power bi",
    "python",
    "react",
    "redis",
    "rust",
    "sql",
    "tailwind",
    "terraform",
    "typescript",
}

_TOKEN_PATTERN = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+#./-]*\b")


def normalize_text(text: str) -> str:
    cleaned = str(text or "").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    return cleaned.strip()


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(text or "")]


def _extract_keywords(text: str) -> list[str]:
    counts: dict[str, int] = {}
    for token in _tokenize(text):
        if token in _STOP_WORDS or len(token) < 3:
            continue
        counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ranked[:25]]


def _extract_skills(text: str) -> list[str]:
    lowered = str(text or "").lower()
    matched = [skill for skill in sorted(_KNOWN_SKILLS) if re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", lowered)]
    if matched:
        return matched[:20]
    return _extract_keywords(text)[:12]


def parse_jd(jd_text: str) -> dict:
    normalized_text = normalize_text(jd_text)
    lines = [line.strip() for line in normalized_text.split("\n") if line.strip()]
    role = next(
        (
            line
            for line in lines
            if any(marker in line.lower() for marker in ("engineer", "developer", "manager", "analyst", "designer"))
        ),
        "",
    )
    keywords = _extract_keywords(normalized_text)
    skills = _extract_skills(normalized_text)
    return {
        "role": role,
        "normalized_text": normalized_text,
        "keywords": keywords,
        "skills": skills,
    }
