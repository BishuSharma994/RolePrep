import unittest

from backend.services.answer_analysis_types import AnswerAnalysisRequest
from backend.services.answer_parser import parse_answer
from backend.services.answer_scorer import score_answer
from backend.services.failure_detector import build_feedback_summary, detect_failures
from backend.services.signal_extractor import extract_signals


class FailureDetectorTests(unittest.TestCase):
    def test_detect_failures_returns_multiple_issues_for_one_sentence(self):
        answer = "We helped improve the system and handled incidents."
        sentences, structure = parse_answer(answer)
        request = AnswerAnalysisRequest(
            role="SRE",
            jd_text="Own production reliability and incident response.",
            current_question="Tell me about an incident you resolved.",
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
        summary = build_feedback_summary(failures, scores)

        issue_types = {issue.type for issue in failures[0].issues}
        self.assertIn("vague", issue_types)
        self.assertIn("weak_ownership", issue_types)
        self.assertIn("no_metric", issue_types)
        self.assertIn("Rejected answer.", summary)
        self.assertIn("fails credibility", summary)


if __name__ == "__main__":
    unittest.main()
