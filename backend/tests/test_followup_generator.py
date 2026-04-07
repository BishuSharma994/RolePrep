import unittest

from backend.services.answer_analysis_types import AnswerAnalysisRequest
from backend.services.answer_parser import parse_answer
from backend.services.answer_scorer import score_answer
from backend.services.failure_detector import detect_failures
from backend.services.followup_generator import generate_followup
from backend.services.signal_extractor import extract_signals


class FollowupGeneratorTests(unittest.TestCase):
    def test_generate_followup_uses_raw_signals_and_failures_without_suppression(self):
        answer = "I redesigned the retry logic so the service became more stable."
        sentences, structure = parse_answer(answer)
        request = AnswerAnalysisRequest(
            role="Backend Engineer",
            jd_text="Improve service reliability and performance.",
            current_question="Describe a reliability improvement you delivered.",
            answer_text=answer,
        )
        signals = extract_signals(
            answer_text=answer,
            sentences=sentences,
            current_question=request.current_question,
            jd_text=request.jd_text,
            parser_data={},
        )
        failures = detect_failures(sentences, signals, context=request)
        scores = score_answer(sentences, structure, signals, request, failures=failures)
        followup = generate_followup(sentences, signals, scores, failures, request)

        self.assertIn("no_metric", followup.triggered_by)
        self.assertIn("measurable terms", followup.question.lower())
        self.assertIn("triggered by", followup.reason.lower())


if __name__ == "__main__":
    unittest.main()
