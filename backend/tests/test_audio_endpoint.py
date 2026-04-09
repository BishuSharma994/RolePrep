import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.audio import router


class AudioEndpointTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix="/api")
        self.client = TestClient(app)

    @patch("backend.api.audio.analyze_answer")
    @patch("backend.api.audio.STTService.transcribe")
    def test_audio_endpoint_returns_transcript_and_analysis(self, mock_transcribe, mock_analyze):
        mock_transcribe.return_value = {
            "transcript": "I reduced latency by 30%.",
            "segments": [
                {"start": 0.0, "end": 3.0, "text": "I reduced latency by 30%."},
            ],
            "pauses": [],
            "pause_count": 0,
            "avg_pause": 0.0,
        }

        class FakeAnalysis:
            def to_dict(self):
                return {"overall_score_100": 82, "feedback_summary": "Rejected answer."}

        mock_analyze.return_value = FakeAnalysis()

        response = self.client.post(
            "/api/analyze-audio",
            files={"file": ("sample.wav", b"fake-audio-bytes", "audio/wav")},
            data={
                "role": "Backend Engineer",
                "jd_text": "Build reliable systems.",
                "current_question": "Tell me about a performance improvement.",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["transcript"], "I reduced latency by 30%.")
        self.assertEqual(payload["segments"][0]["text"], "I reduced latency by 30%.")
        self.assertEqual(payload["analysis"]["overall_score_100"], 82)
        self.assertEqual(payload["analysis"]["content"]["overall_score_100"], 82)
        self.assertEqual(payload["analysis"]["voice"]["filler_count"], 0)
        self.assertEqual(payload["audio_metrics"]["pause_count"], 0)
        self.assertFalse(payload["session_updated"])
        self.assertIsNone(payload["session"])

    @patch("backend.api.audio._get_session")
    @patch("backend.api.audio._record_answer_analysis")
    @patch("backend.api.audio.analyze_answer")
    @patch("backend.api.audio.STTService.transcribe")
    def test_audio_endpoint_updates_session_when_user_id_is_present(
        self,
        mock_transcribe,
        mock_analyze,
        mock_record_answer_analysis,
        mock_get_session,
    ):
        mock_transcribe.return_value = {
            "transcript": "I improved reliability by 20%.",
            "segments": [],
            "pauses": [],
            "pause_count": 0,
            "avg_pause": 0.0,
        }

        class FakeAnalysis:
            def to_dict(self):
                return {
                    "overall_score_100": 88,
                    "legacy_score_10": 8.4,
                    "feedback_summary": "Strong answer.",
                    "next_question": "What trade-off did you make?",
                    "followup": {"question": "What trade-off did you make?", "requires_stage_change": False},
                }

        mock_analyze.return_value = FakeAnalysis()
        mock_record_answer_analysis.return_value = True
        mock_get_session.return_value = {
            "session_id": "session-1",
            "current_question": "What trade-off did you make?",
            "current_stage": "interview",
            "question_count": 1,
            "scores": [8.4],
            "latest_answer_analysis": {"overall_score_100": 88},
        }

        response = self.client.post(
            "/api/analyze-audio",
            files={"file": ("sample.wav", b"fake-audio-bytes", "audio/wav")},
            data={
                "user_id": "user-123",
                "role": "Backend Engineer",
                "jd_text": "Build reliable systems.",
                "current_question": "Tell me about a performance improvement.",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["session_updated"])
        self.assertEqual(payload["session"]["user_id"], "user-123")
        self.assertEqual(payload["session"]["question_count"], 1)
        self.assertEqual(payload["session"]["current_question"], "What trade-off did you make?")
        mock_record_answer_analysis.assert_called_once()


if __name__ == "__main__":
    unittest.main()
