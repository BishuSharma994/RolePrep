import unittest

from backend.services.answer_analysis_types import AnswerAnalysisRequest
from backend.services.answer_parser import parse_answer
from backend.services.answer_scorer import map_score_100_to_legacy_10, score_answer
from backend.services.signal_extractor import extract_signals


class AnswerScorerTests(unittest.TestCase):
    def test_score_answer_rewards_specific_evidence(self):
        answer = (
            "I own the ingestion service for our analytics platform. "
            "For example, I rewrote the Python batching logic, cut processing time by 48%, "
            "and removed 3 daily failure modes. "
            "As a result, the pipeline cleared on time for 99.5% of runs."
        )
        sentences, structure = parse_answer(answer)
        request = AnswerAnalysisRequest(
            role="Backend Engineer",
            jd_text="Build reliable Python data services.",
            current_question="Tell me about a project you owned end to end.",
            answer_text=answer,
        )
        signals = extract_signals(
            answer_text=answer,
            sentences=sentences,
            current_question=request.current_question,
            jd_text=request.jd_text,
            parser_data={},
        )
        scores = score_answer(sentences, structure, signals, request)

        self.assertGreaterEqual(scores.total, 70)
        self.assertGreaterEqual(map_score_100_to_legacy_10(scores.total, answer), 7.0)


if __name__ == "__main__":
    unittest.main()
