"""Test script for send_email_reply() with a real recipient.

Usage:
    python test_send_email_reply.py

Make sure .env contains:
    SMTP_SERVER=smtp.gmail.com
    SMTP_PORT=587
    SMTP_EMAIL=yourgmail@gmail.com
    SMTP_PASSWORD=your_app_password
    SMTP_MOCK_MODE=false

"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from app.email.send_email import send_email_reply

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOGGER = logging.getLogger(__name__)


def verify_env():
    required = ["SMTP_EMAIL", "SMTP_PASSWORD", "SMTP_SERVER", "SMTP_PORT"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        LOGGER.error("Missing env vars: %s", ", ".join(missing))
        return False
    if os.getenv("SMTP_MOCK_MODE", "true").lower() == "true":
        LOGGER.warning("SMTP_MOCK_MODE=true; this script will not send a real email.")
        return False
    return True


def run_test():
    if not verify_env():
        LOGGER.error("Fix .env values and set SMTP_MOCK_MODE=false then rerun.")
        return

    to_email = "sakshikukreja2005@gmail.com"
    subject = "Test: SalesAI SMTP Direct Reply"
    body = "This is a test email from SalesAI. If you receive it, SMTP is working."

    LOGGER.info("Sending test email to %s", to_email)
    sent = send_email_reply(to=to_email, subject=subject, body=body)

    if sent:
        LOGGER.info("Test email send_email_reply() succeeded.")
    else:
        LOGGER.error("Test email send_email_reply() failed.")


if __name__ == "__main__":
    run_test()
