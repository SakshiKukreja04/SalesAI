"""Email sending logic using SMTP.

This module provides a simple helper to send outbound support replies.
"""

import smtplib
from email.mime.text import MIMEText

from app.config import settings


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send an email through SMTP and return success status."""
    if not settings.smtp_email or not settings.smtp_password:
        # Safe local fallback for development when SMTP is not configured.
        print(f"[MOCK SMTP] To: {to_email} | Subject: {subject}\n{body}")
        return True

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_email, settings.smtp_password)
            server.sendmail(settings.smtp_email, [to_email], msg.as_string())
        return True
    except Exception as exc:
        print(f"SMTP send failed: {exc}")
        return False
