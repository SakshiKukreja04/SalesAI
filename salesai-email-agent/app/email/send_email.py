"""Email sending logic using SMTP.

This module provides a simple helper to send outbound support replies.
"""

import logging
import smtplib
from email.mime.text import MIMEText

from app.config import settings


LOGGER = logging.getLogger(__name__)


def _with_signature(body: str) -> str:
    """Append configured signature unless it already exists in reply body."""
    content = (body or "").strip()
    signature = (settings.reply_signature or "").strip()
    if not signature:
        return content

    if signature.lower() in content.lower():
        return content

    if not content:
        return signature

    return f"{content}\n\n{signature}"


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send an email through SMTP and return success status."""
    final_body = _with_signature(body)

    if settings.smtp_mock_mode:
        # Safe local fallback for development when SMTP is not configured.
        print(f"[MOCK SMTP] To: {to_email} | Subject: {subject}\n{final_body}")
        LOGGER.info("SMTP mock mode is enabled. No real email was sent.")
        return True

    if not settings.smtp_email or not settings.smtp_password:
        LOGGER.error("SMTP_EMAIL/SMTP_PASSWORD are required when SMTP_MOCK_MODE=false")
        return False

    msg = MIMEText(final_body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_email, settings.smtp_password)
            server.sendmail(settings.smtp_email, [to_email], msg.as_string())
        LOGGER.info("SMTP email sent to %s", to_email)
        return True
    except Exception as exc:
        LOGGER.exception("SMTP send failed: %s", exc)
        return False
