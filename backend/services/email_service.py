"""Email service: SendGrid API or SMTP fallback."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Raised when email delivery fails."""
    pass


def send_email(to_email: str, subject: str, html_body: str, text_body: str | None = None) -> None:
    """Send an email using the configured provider."""
    settings = get_settings()
    if settings.email_provider == "sendgrid" and settings.sendgrid_api_key:
        _send_via_sendgrid(to_email, subject, html_body, text_body, settings)
    else:
        _send_via_smtp(to_email, subject, html_body, text_body, settings)


def _send_via_sendgrid(to_email: str, subject: str, html_body: str, text_body: str | None, settings) -> None:
    """Send email via SendGrid API."""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content

        message = Mail(
            from_email=Email(settings.email_from_address, settings.email_from_name),
            to_emails=To(to_email),
            subject=subject,
        )
        message.add_content(Content("text/html", html_body))
        if text_body:
            message.add_content(Content("text/plain", text_body))

        sg = SendGridAPIClient(settings.sendgrid_api_key)
        response = sg.send(message)
        logger.info("Email sent via SendGrid to %s (status=%s)", to_email, response.status_code)
    except Exception as exc:
        logger.exception("SendGrid email delivery failed to %s", to_email)
        raise EmailSendError("Email delivery failed") from exc


def _send_via_smtp(to_email: str, subject: str, html_body: str, text_body: str | None, settings) -> None:
    """Send email via SMTP."""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.email_from_name} <{settings.email_from_address}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)

        logger.info("Email sent via SMTP to %s", to_email)
    except Exception as exc:
        logger.exception("SMTP email delivery failed to %s", to_email)
        raise EmailSendError("Email delivery failed") from exc
