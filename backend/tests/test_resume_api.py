import base64
import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi import HTTPException
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.resume import router


class _FakeResumeCollection:
    def __init__(self):
        self.inserted = []
        self.document = None

    def insert_one(self, document):
        self.inserted.append(document)

        class Result:
            acknowledged = True

        return Result()

    def find_one(self, *_args, **_kwargs):
        return self.document


class ResumeApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix="/api")
        self.client = TestClient(app)

    @patch("backend.api.resume._generate_pdf")
    @patch("backend.api.resume._build_resume")
    @patch("backend.api.resume._resume_input_from_text")
    @patch("backend.api.resume._parse_jd")
    @patch("backend.api.resume._require_paid_resume_access")
    @patch("backend.api.resume._normalize_resume_user_id")
    def test_generate_resume_returns_json_and_pdf(
        self,
        mock_normalize_user_id,
        mock_require_paid_resume_access,
        mock_parse_jd,
        mock_resume_input,
        mock_build_resume,
        mock_generate_pdf,
    ):
        fake_collection = _FakeResumeCollection()
        mock_normalize_user_id.return_value = "user-123"
        mock_parse_jd.return_value = {"role": "Backend Engineer", "keywords": ["python"], "skills": ["python"]}
        mock_resume_input.return_value = {"bullets": ["Built APIs."], "skills": ["python"]}
        mock_build_resume.return_value = {
            "summary": "Summary",
            "skills": ["python"],
            "experience": [{"title": "Experience 1", "bullets": ["Built APIs."]}],
            "projects": [],
        }
        mock_generate_pdf.return_value = b"%PDF-test"

        with patch("backend.api.resume._get_resumes_collection", return_value=fake_collection):
            response = self.client.post(
                "/api/resume/generate",
                json={
                    "user_id": "user-123",
                    "jd_text": "Backend Engineer with Python",
                    "raw_text": "Built APIs and improved performance by 20%.",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "generated")
        self.assertEqual(payload["user_id"], "user-123")
        self.assertEqual(payload["resume_json"]["summary"], "Summary")
        self.assertEqual(payload["content_type"], "application/pdf")
        self.assertEqual(base64.b64decode(payload["pdf_base64"]), b"%PDF-test")
        self.assertEqual(len(fake_collection.inserted), 1)
        mock_require_paid_resume_access.assert_called_once_with("user-123")

    @patch("backend.api.resume._generate_pdf")
    @patch("backend.api.resume._require_paid_resume_access")
    @patch("backend.api.resume._normalize_resume_user_id")
    def test_get_resume_returns_latest_resume(self, mock_normalize_user_id, mock_require_paid_resume_access, mock_generate_pdf):
        fake_collection = _FakeResumeCollection()
        fake_collection.document = {
            "user_id": "user-123",
            "jd_text": "Backend Engineer with Python",
            "resume_json": {
                "summary": "Summary",
                "skills": ["python"],
                "experience": [],
                "projects": [],
            },
            "created_at": datetime.utcnow(),
        }
        mock_normalize_user_id.return_value = "user-123"
        mock_generate_pdf.return_value = b"%PDF-test"

        with patch("backend.api.resume._get_resumes_collection", return_value=fake_collection):
            response = self.client.get("/api/resume/user-123")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user_id"], "user-123")
        self.assertEqual(base64.b64decode(payload["pdf_base64"]), b"%PDF-test")
        mock_require_paid_resume_access.assert_called_once_with("user-123")

    def test_generate_resume_blocks_free_users(self):
        with patch("backend.api.resume._normalize_resume_user_id", return_value="free-user"), patch(
            "backend.api.resume._require_paid_resume_access",
            side_effect=HTTPException(
                status_code=403,
                detail={
                    "code": "RESUME_PLAN_REQUIRED",
                    "reason": "resume_access_requires_paid_plan",
                    "message": "Resume generation is available only on paid plans.",
                },
            ),
        ):
            response = self.client.post(
                "/api/resume/generate",
                json={
                    "user_id": "free-user",
                    "jd_text": "Backend Engineer with Python",
                    "raw_text": "Built APIs and improved performance by 20%.",
                },
            )

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertEqual(payload["detail"]["code"], "RESUME_PLAN_REQUIRED")

    def test_get_resume_blocks_free_users(self):
        with patch("backend.api.resume._normalize_resume_user_id", return_value="free-user"), patch(
            "backend.api.resume._require_paid_resume_access",
            side_effect=HTTPException(
                status_code=403,
                detail={
                    "code": "RESUME_PLAN_REQUIRED",
                    "reason": "resume_access_requires_paid_plan",
                    "message": "Resume generation is available only on paid plans.",
                },
            ),
        ):
            response = self.client.get("/api/resume/free-user")

        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertEqual(payload["detail"]["reason"], "resume_access_requires_paid_plan")


if __name__ == "__main__":
    unittest.main()
