import unittest
from unittest.mock import Mock, patch

from backend import auth_service


class AuthDeliveryTests(unittest.TestCase):
    @patch("backend.auth_service.ZEPTO_SEND_MAIL_TOKEN", "Zoho-enczapikey token")
    @patch("backend.auth_service.ZEPTO_FROM_EMAIL", "support@roleprep.in")
    @patch("backend.auth_service.ZEPTO_FROM_NAME", "RolePrep")
    @patch("backend.auth_service.ZEPTO_API_HOST", "api.zeptomail.in")
    @patch("backend.auth_service.ZEPTO_API_URL", None)
    def test_otp_delivery_configured_when_zepto_present(self):
        self.assertTrue(auth_service.otp_delivery_configured())

    @patch("backend.auth_service.ZEPTO_SEND_MAIL_TOKEN", "Zoho-enczapikey token")
    @patch("backend.auth_service.ZEPTO_FROM_EMAIL", "support@roleprep.in")
    @patch("backend.auth_service.ZEPTO_FROM_NAME", "RolePrep")
    @patch("backend.auth_service.ZEPTO_API_HOST", "api.zeptomail.in")
    @patch("backend.auth_service.ZEPTO_API_URL", None)
    @patch("backend.auth_service.requests.post")
    def test_send_otp_prefers_zepto_delivery(self, mock_post):
        mock_post.return_value = Mock(status_code=200, text='{"data":[]}')

        auth_service._send_otp_email("user@example.com", "123456")

        mock_post.assert_called_once()
        kwargs = mock_post.call_args.kwargs
        self.assertEqual(kwargs["headers"]["authorization"], "Zoho-enczapikey token")
        self.assertEqual(kwargs["json"]["from"]["address"], "support@roleprep.in")
        self.assertEqual(kwargs["json"]["to"][0]["email_address"]["address"], "user@example.com")


if __name__ == "__main__":
    unittest.main()
