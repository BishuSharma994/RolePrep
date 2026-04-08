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


if __name__ == "__main__":
    unittest.main()
