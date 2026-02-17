"""Tests for email service — SMTP and SendGrid providers."""

import pytest
from unittest.mock import patch, MagicMock

from backend.services.email_service import send_email, EmailSendError


class TestEmailServiceSMTP:
    """SMTP provider tests."""

    @patch("backend.services.email_service.smtplib.SMTP")
    def test_smtp_send_success(self, mock_smtp_class):
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        with patch("backend.services.email_service.get_settings") as mock_settings:
            settings = mock_settings.return_value
            settings.email_provider = "smtp"
            settings.smtp_host = "localhost"
            settings.smtp_port = 587
            settings.smtp_use_tls = True
            settings.smtp_username = "user"
            settings.smtp_password = "pass"
            settings.email_from_address = "noreply@test.com"
            settings.email_from_name = "Test"
            settings.sendgrid_api_key = ""

            send_email("user@test.com", "Test Subject", "<p>Hello</p>", "Hello")

        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.send_message.assert_called_once()

    @patch("backend.services.email_service.smtplib.SMTP")
    def test_smtp_send_without_tls(self, mock_smtp_class):
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        with patch("backend.services.email_service.get_settings") as mock_settings:
            settings = mock_settings.return_value
            settings.email_provider = "smtp"
            settings.smtp_host = "localhost"
            settings.smtp_port = 25
            settings.smtp_use_tls = False
            settings.smtp_username = ""
            settings.smtp_password = ""
            settings.email_from_address = "noreply@test.com"
            settings.email_from_name = "Test"
            settings.sendgrid_api_key = ""

            send_email("user@test.com", "Test", "<p>Hi</p>")

        mock_server.starttls.assert_not_called()
        mock_server.login.assert_not_called()

    @patch("backend.services.email_service.smtplib.SMTP")
    def test_smtp_send_failure_raises_email_send_error(self, mock_smtp_class):
        mock_smtp_class.side_effect = ConnectionRefusedError("Connection refused")

        with patch("backend.services.email_service.get_settings") as mock_settings:
            settings = mock_settings.return_value
            settings.email_provider = "smtp"
            settings.smtp_host = "localhost"
            settings.smtp_port = 587
            settings.smtp_use_tls = True
            settings.smtp_username = ""
            settings.smtp_password = ""
            settings.email_from_address = "noreply@test.com"
            settings.email_from_name = "Test"
            settings.sendgrid_api_key = ""

            with pytest.raises(EmailSendError):
                send_email("user@test.com", "Test", "<p>Fail</p>")


class TestEmailServiceSendGrid:
    """SendGrid provider tests."""

    @patch("backend.services.email_service.get_settings")
    def test_sendgrid_send_success(self, mock_settings):
        settings = mock_settings.return_value
        settings.email_provider = "sendgrid"
        settings.sendgrid_api_key = "SG.test_key"
        settings.email_from_address = "noreply@test.com"
        settings.email_from_name = "Test"

        with patch("sendgrid.SendGridAPIClient") as mock_sg_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 202
            mock_client.send.return_value = mock_response
            mock_sg_class.return_value = mock_client

            send_email("user@test.com", "Test Subject", "<p>Hello</p>", "Hello")

            mock_client.send.assert_called_once()

    @patch("backend.services.email_service.get_settings")
    def test_sendgrid_send_failure_raises_email_send_error(self, mock_settings):
        settings = mock_settings.return_value
        settings.email_provider = "sendgrid"
        settings.sendgrid_api_key = "SG.test_key"
        settings.email_from_address = "noreply@test.com"
        settings.email_from_name = "Test"

        with patch("sendgrid.SendGridAPIClient") as mock_sg_class:
            mock_client = MagicMock()
            mock_client.send.side_effect = Exception("API error")
            mock_sg_class.return_value = mock_client

            with pytest.raises(EmailSendError):
                send_email("user@test.com", "Test", "<p>Fail</p>")


class TestEmailProviderRouting:
    """Tests that provider routing works correctly."""

    @patch("backend.services.email_service._send_via_sendgrid")
    @patch("backend.services.email_service.get_settings")
    def test_routes_to_sendgrid_when_configured(self, mock_settings, mock_sendgrid):
        settings = mock_settings.return_value
        settings.email_provider = "sendgrid"
        settings.sendgrid_api_key = "SG.key"

        send_email("user@test.com", "Test", "<p>Hi</p>")

        mock_sendgrid.assert_called_once()

    @patch("backend.services.email_service._send_via_smtp")
    @patch("backend.services.email_service.get_settings")
    def test_routes_to_smtp_by_default(self, mock_settings, mock_smtp):
        settings = mock_settings.return_value
        settings.email_provider = "smtp"
        settings.sendgrid_api_key = ""

        send_email("user@test.com", "Test", "<p>Hi</p>")

        mock_smtp.assert_called_once()
