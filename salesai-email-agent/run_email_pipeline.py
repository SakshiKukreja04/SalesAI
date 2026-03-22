"""Step-1 execution script for SalesAI Email Agent.

This script demonstrates:
- Fetching unread emails from Gmail
- Cleaning and normalizing message text
- Extracting key fields
- Printing structured console output for demo
"""

import logging
import re
import time
from typing import Dict, List

from app.db.supabase_client import create_table_if_not_exists, insert_email_data
from app.email.fetch_emails import fetch_unread_emails
from app.nlp.emotion import detect_emotion_for_email
from app.nlp.intent import classify_intent_for_email


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Normalize text by collapsing whitespace and removing control chars."""
    if not text:
        return ""

    normalized = re.sub(r"[\r\t]+", " ", text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _process_email(email: Dict[str, str]) -> Dict[str, str]:
    """Process an email: clean text, detect intent/emotion, log, and return extended record."""
    email_id = email.get("id", "")
    sender = email.get("from", "")
    subject = email.get("subject", "")
    timestamp = email.get("timestamp", "")

    body = clean_text(email.get("body", ""))
    if not body:
        body = "[No readable body content]"

    logger.info("Email received: id=%s sender=%s subject=%s", email_id, sender, subject)

    try:
        intent_result = classify_intent_for_email(email_id=email_id, text=body)
        intent = intent_result.get("intent", "unknown")
        logger.info("Intent detected: id=%s intent=%s", email_id, intent)
    except Exception:
        intent = "unknown"
        logger.exception("Intent detection failed for email id=%s", email_id)

    try:
        emotion_result = detect_emotion_for_email(email_id=email_id, text=body)
        emotion = emotion_result.get("emotion", "unknown")
        logger.info("Emotion detected: id=%s emotion=%s", email_id, emotion)
    except Exception:
        emotion = "unknown"
        logger.exception("Emotion detection failed for email id=%s", email_id)

    processed = {
        "id": email_id,
        "from": sender,
        "subject": subject,
        "body": body,
        "timestamp": timestamp,
        "intent": intent,
        "emotion": emotion,
    }

    return processed


def run_email_pipeline(interval: int = 30, poll_forever: bool = False) -> None:
    """Fetch unread emails, process them, and store results in PostgreSQL.

    When poll_forever is True, this function runs continuously and polls every
    `interval` seconds.
    """
    try:
        create_table_if_not_exists()
    except Exception:
        logger.exception("Failed to ensure customer_emails table exists. Aborting pipeline.")
        return

    while True:
        logger.info("Polling Gmail Inbox...")

        try:
            emails: List[Dict[str, str]] = fetch_unread_emails()
        except Exception:
            logger.exception("Failed to fetch unread emails")
            if not poll_forever:
                return
            time.sleep(interval)
            continue

        if not emails:
            logger.info("No new emails")
        else:
            for email in emails:
                try:
                    processed = _process_email(email)
                    insert_email_data(processed)
                    logger.info("Email data stored: id=%s", processed.get("id"))
                except Exception:
                    logger.exception("Failed to process and store email id=%s", email.get("id", "unknown"))

        if not poll_forever:
            return

        time.sleep(interval)


if __name__ == "__main__":
    run_email_pipeline()

