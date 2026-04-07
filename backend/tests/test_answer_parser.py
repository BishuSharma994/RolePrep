import unittest

from backend.services.answer_parser import parse_answer


class AnswerParserTests(unittest.TestCase):
    def test_parse_answer_detects_sections(self):
        sentences, structure = parse_answer(
            "I am a backend engineer focused on platform reliability. "
            "For example, I redesigned our retry flow and cut timeout failures by 42%. "
            "As a result, incident volume dropped and support tickets fell."
        )

        self.assertEqual(len(sentences), 3)
        self.assertEqual(sentences[0].section, "intro")
        self.assertEqual(sentences[1].section, "example")
        self.assertEqual(sentences[2].section, "conclusion")
        self.assertEqual(structure.example_count, 1)


if __name__ == "__main__":
    unittest.main()
