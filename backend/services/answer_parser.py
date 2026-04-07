from __future__ import annotations

import re

from backend.services.answer_analysis_types import AnswerStructure, SentenceUnit, StructuredSentence

_CONNECTOR_WORDS = {
    "and",
    "but",
    "because",
    "so",
    "then",
    "therefore",
    "however",
    "overall",
    "finally",
    "also",
}
_INTRO_MARKERS = (
    "i am",
    "i'm",
    "my background",
    "currently",
    "in my current role",
    "over the last",
)
_EXAMPLE_MARKERS = (
    "for example",
    "for instance",
    "one example",
    "for a recent project",
    "in one project",
    "at my last company",
    "when i",
    "i led",
    "i built",
    "i designed",
    "i implemented",
    "i owned",
)
_CONCLUSION_MARKERS = (
    "as a result",
    "overall",
    "ultimately",
    "in the end",
    "that led to",
    "so the result was",
    "the outcome was",
)
_RESULT_MARKERS = (
    "increased",
    "reduced",
    "improved",
    "cut",
    "saved",
    "grew",
    "delivered",
    "launched",
    "resulted",
    "led to",
)
_ABBREVIATIONS = (
    "e.g.",
    "i.e.",
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "sr.",
    "jr.",
    "etc.",
)
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")
_TOKEN_PATTERN = re.compile(r"\b[\w%]+\b")


def normalize_answer(text: str) -> str:
    cleaned = (text or "").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)
    return cleaned.strip()


def _protect_abbreviations(text: str) -> str:
    protected = text
    for abbreviation in _ABBREVIATIONS:
        protected = protected.replace(abbreviation, abbreviation.replace(".", "<prd>"))
    return protected


def _restore_abbreviations(text: str) -> str:
    return text.replace("<prd>", ".")


def split_sentences(text: str) -> list[SentenceUnit]:
    normalized = normalize_answer(text)
    if not normalized:
        return []

    protected = _protect_abbreviations(normalized)
    raw_parts = _SENTENCE_SPLIT_PATTERN.split(protected)

    sentences: list[SentenceUnit] = []
    for index, part in enumerate(raw_parts):
        restored = _restore_abbreviations(part).strip(" -")
        if not restored:
            continue
        tokens = _TOKEN_PATTERN.findall(restored)
        first_token = tokens[0].lower() if tokens else ""
        sentences.append(
            SentenceUnit(
                index=len(sentences),
                text=restored,
                token_count=len(tokens),
                starts_with_connector=first_token in _CONNECTOR_WORDS,
                ends_cleanly=restored[-1:] in {".", "!", "?"} or len(restored) <= 25,
            )
        )
    return sentences


def _looks_like_intro(sentence: SentenceUnit, total_sentences: int) -> bool:
    lower_text = sentence.text.lower()
    return sentence.index == 0 and (
        any(marker in lower_text for marker in _INTRO_MARKERS)
        or total_sentences <= 2
    )


def _looks_like_example(sentence: SentenceUnit) -> bool:
    lower_text = sentence.text.lower()
    return any(marker in lower_text for marker in _EXAMPLE_MARKERS) or (
        any(marker in lower_text for marker in _RESULT_MARKERS)
        and bool(re.search(r"\b\d", lower_text))
    )


def _looks_like_conclusion(sentence: SentenceUnit, total_sentences: int) -> bool:
    lower_text = sentence.text.lower()
    return sentence.index == total_sentences - 1 and (
        any(marker in lower_text for marker in _CONCLUSION_MARKERS)
        or any(marker in lower_text for marker in _RESULT_MARKERS)
    )


def detect_sections(sentences: list[SentenceUnit]) -> list[StructuredSentence]:
    structured: list[StructuredSentence] = []
    total_sentences = len(sentences)

    for sentence in sentences:
        section = "body"
        if _looks_like_intro(sentence, total_sentences):
            section = "intro"
        elif _looks_like_example(sentence):
            section = "example"
        elif _looks_like_conclusion(sentence, total_sentences):
            section = "conclusion"
        elif sentence.token_count <= 3:
            section = "unclassified"

        structured.append(
            StructuredSentence(
                index=sentence.index,
                text=sentence.text,
                token_count=sentence.token_count,
                starts_with_connector=sentence.starts_with_connector,
                ends_cleanly=sentence.ends_cleanly,
                section=section,
            )
        )

    return structured


def classify_answer_shape(sentences: list[StructuredSentence]) -> AnswerStructure:
    structure = AnswerStructure()
    for sentence in sentences:
        if sentence.section == "intro":
            structure.intro_count += 1
        elif sentence.section == "body":
            structure.body_count += 1
        elif sentence.section == "example":
            structure.example_count += 1
        elif sentence.section == "conclusion":
            structure.conclusion_count += 1
        else:
            structure.unclassified_count += 1

    if structure.example_count and structure.conclusion_count:
        structure.dominant_shape = "evidence_backed"
    elif structure.example_count:
        structure.dominant_shape = "example_led"
    elif structure.body_count >= 2:
        structure.dominant_shape = "explanatory"
    elif sentences:
        structure.dominant_shape = "minimal"

    return structure


def parse_answer(text: str) -> tuple[list[StructuredSentence], AnswerStructure]:
    sentences = split_sentences(text)
    structured = detect_sections(sentences)
    return structured, classify_answer_shape(structured)
