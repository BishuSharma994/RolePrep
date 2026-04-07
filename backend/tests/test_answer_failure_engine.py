import unittest

from backend.services.answer_analysis_types import AnswerAnalysisRequest
from backend.services.answer_failure_engine import analyze_answer


class AnswerFailureEngineTests(unittest.TestCase):
    def test_analyze_answer_returns_backward_compatible_response(self):
        request = AnswerAnalysisRequest(
            role="Backend Engineer",
            jd_text="Build Python APIs and improve service reliability.",
            current_question="Tell me about a project where you improved system performance.",
            answer_text=(
                "I owned an API latency issue in our Python service. "
                "For example, I removed blocking queries, added batching, and cut p95 latency by 41%. "
                "As a result, error rates dropped and checkout completion improved."
            ),
        )

        result = analyze_answer(request)

        self.assertIn("score", result.compat_response)
        self.assertIn("feedback", result.compat_response)
        self.assertIn("next_question", result.compat_response)
        self.assertIn("analysis", result.compat_response)
        self.assertGreaterEqual(result.compat_response["score"], 7.0)
        self.assertEqual(result.compat_response["analysis"]["overall_score_100"], result.overall_score_100)


if __name__ == "__main__":
    unittest.main()
