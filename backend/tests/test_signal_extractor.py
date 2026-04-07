import unittest

from backend.services.answer_parser import parse_answer
from backend.services.signal_extractor import extract_signals


class SignalExtractorTests(unittest.TestCase):
    def test_extract_signals_detects_metrics_vagueness_ownership_tools_fillers_and_impact(self):
        answer = "Basically, we helped migrate a Python service and reduced failures by 35%."
        sentences, _ = parse_answer(answer)
        signals = extract_signals(
            answer_text=answer,
            sentences=sentences,
            current_question="Tell me about a reliability improvement you led.",
            jd_text="Python backend engineer working on services and reliability.",
            parser_data={},
        )

        self.assertGreaterEqual(signals.metric_count, 1)
        self.assertGreaterEqual(signals.impact_count, 1)
        self.assertGreaterEqual(signals.vague_phrase_count, 1)
        self.assertEqual(signals.ownership_strength, "weak")
        self.assertTrue(any(tool.tool == "python" for tool in signals.tools))
        self.assertGreaterEqual(signals.filler_count, 1)


if __name__ == "__main__":
    unittest.main()
