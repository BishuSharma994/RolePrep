import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.account import router


class AccountApiTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix="/api")
        self.client = TestClient(app)

    @patch("backend.api.account._create_link_code")
    def test_create_link_code_returns_ready_payload(self, mock_create_link_code):
        mock_create_link_code.return_value = {
            "code": "AB12CD34",
            "expires_at": 1_700_000_000,
            "expires_in_seconds": 600,
        }

        response = self.client.post("/api/account/link-code", json={"user_id": "user-123"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "ready",
                "code": "AB12CD34",
                "expires_at": 1_700_000_000,
                "expires_in_seconds": 600,
            },
        )

    @patch("backend.api.account._consume_link_code")
    def test_link_account_returns_linked_user(self, mock_consume_link_code):
        mock_consume_link_code.return_value = "paid-user-456"

        response = self.client.post(
            "/api/account/link",
            json={"user_id": "mobile-device-1", "code": "AB12CD34"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "linked",
                "user_id": "paid-user-456",
            },
        )


if __name__ == "__main__":
    unittest.main()
