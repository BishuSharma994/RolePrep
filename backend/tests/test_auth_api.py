import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.auth import router


class AuthApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix="/api")
        self.client = TestClient(app)

    @patch("backend.api.auth._request_email_otp")
    def test_request_otp_returns_sent_payload(self, mock_request_email_otp):
        mock_request_email_otp.return_value = {
            "status": "sent",
            "email": "person@example.com",
            "expires_in_seconds": 600,
            "debug_otp": "123456",
        }

        response = self.client.post("/api/auth/request-otp", json={"email": "person@example.com"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "sent")
        self.assertEqual(response.json()["email"], "person@example.com")

    def test_auth_config_returns_flags(self):
        response = self.client.get("/api/auth/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("auth_required", payload)
        self.assertIn("anonymous_mode_allowed", payload)
        self.assertIn("otp_login_enabled", payload)
        self.assertTrue(payload["account_sync_enabled"])

    @patch("backend.api.auth._verify_email_otp")
    def test_verify_otp_returns_auth_payload(self, mock_verify_email_otp):
        mock_verify_email_otp.return_value = {
            "status": "authenticated",
            "user_id": "user-123",
            "email": "person@example.com",
            "auth_token": "token-abc",
            "expires_at": 1_700_000_000,
        }

        response = self.client.post(
            "/api/auth/verify-otp",
            json={"email": "person@example.com", "otp": "123456", "user_id": "local-user-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "authenticated")
        self.assertEqual(response.json()["user_id"], "user-123")
        self.assertEqual(response.json()["auth_token"], "token-abc")

    @patch("backend.api.auth._get_auth_session_from_header")
    def test_get_auth_session_returns_authenticated_session(self, mock_get_auth_session):
        mock_get_auth_session.return_value = {
            "user_id": "user-123",
            "email": "person@example.com",
            "expires_at": 1_700_000_000,
        }

        response = self.client.get("/api/auth/session", headers={"Authorization": "Bearer token-abc"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "authenticated")
        self.assertEqual(response.json()["user_id"], "user-123")

    @patch("backend.api.auth._revoke_auth_session")
    def test_logout_returns_logged_out_status(self, mock_revoke_auth_session):
        response = self.client.post("/api/auth/logout", headers={"Authorization": "Bearer token-abc"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "logged_out"})
        mock_revoke_auth_session.assert_called_once()


if __name__ == "__main__":
    unittest.main()
