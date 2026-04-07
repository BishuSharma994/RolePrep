import unittest

from backend.services.answer_analysis_types import AnswerAnalysisRequest
from backend.services.answer_failure_engine import analyze_answer


class AnswerFailureRegressionTests(unittest.TestCase):
    def test_regression_sample_produces_multiple_failures(self):
        answer = "I worked on improving team processes and helped increase efficiency."
        request = AnswerAnalysisRequest(
            role="Backend Engineer",
            jd_text="Drive operational efficiency, ownership, and measurable impact.",
            current_question="Tell me about a process improvement you led.",
            answer_text=answer,
        )

        result = analyze_answer(request)
        issues = result.failures[0].issues
        issue_types = {issue.type for issue in issues}

        self.assertGreaterEqual(len(issues), 3)
        self.assertIn("vague", issue_types)
        self.assertIn("weak_ownership", issue_types)
        self.assertIn("no_metric", issue_types)
        self.assertIn("'worked on'", " ".join(issue.reason for issue in issues))
        self.assertIn("'helped'", " ".join(issue.reason for issue in issues))

    def test_regression_sample_feedback_is_harsh_not_generic(self):
        answer = "I worked on improving team processes and helped increase efficiency."
        request = AnswerAnalysisRequest(
            role="Backend Engineer",
            jd_text="Drive operational efficiency, ownership, and measurable impact.",
            current_question="Tell me about a process improvement you led.",
            answer_text=answer,
        )

        result = analyze_answer(request)
        summary = result.feedback_summary.lower()

        self.assertIn("rejected answer", summary)
        self.assertIn("fails credibility", summary)
        self.assertNotIn("usable answer", summary)
        self.assertNotIn("improve clarity", summary)

    def test_regression_sample_followup_demands_impact_and_specifics(self):
        answer = "I worked on improving team processes and helped increase efficiency."
        request = AnswerAnalysisRequest(
            role="Backend Engineer",
            jd_text="Drive operational efficiency, ownership, and measurable impact.",
            current_question="Tell me about a process improvement you led.",
            answer_text=answer,
        )

        result = analyze_answer(request)
        followup = result.followup
        question = followup.question.lower()

        self.assertIn("no_metric", followup.triggered_by)
        self.assertIn("vague", followup.triggered_by)
        self.assertIn("weak_ownership", followup.triggered_by)
        self.assertIn("numbers", question)
        self.assertIn("exact action", question)
        self.assertIn("personally own", question)


if __name__ == "__main__":
    unittest.main()
