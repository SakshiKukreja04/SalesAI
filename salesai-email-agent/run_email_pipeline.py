"""Step-1 execution script for SalesAI Email Agent.

This script demonstrates:
- Fetching unread emails from Gmail
- Cleaning and normalizing message text
- Extracting key fields
- Printing structured console output for demo
- Avoiding duplicate email processing
- Filtering system emails
"""

import logging
import re
import time
from typing import Dict, List, Set

from app.agents.orchestrator import handle_customer_email
from app.db.supabase_client import (
    check_email_already_replied,
    create_table_if_not_exists,
    get_replied_email_ids,
    insert_email_data,
    reserve_email_for_processing,
    update_email_processing_status,
)
from app.email.fetch_emails import fetch_unread_emails, mark_email_as_read
from app.email.send_email import extract_customer_name
from app.nlp.emotion import detect_emotion_for_email
from app.nlp.intent import classify_intent_for_email
from app.rag.chroma_store import ensure_collection, refresh_knowledge_embeddings


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Track processed emails to avoid duplicate processing
processed_email_ids: Set[str] = set()

# System email patterns to ignore
SYSTEM_EMAIL_PATTERNS = [
    "no-reply",
    "noreply",
    "accounts.google.com",
    "google.com",
    "mailer-daemon",
    "notifications",
    "support@google",
    "postmaster",
]


def _extract_sender_email(sender_value: str) -> str:
    """Extract plain email address from Gmail From header value."""
    if not sender_value:
        return ""

    match = re.search(r"<([^>]+)>", sender_value)
    if match:
        return match.group(1).strip()
    return sender_value.strip()


def clean_text(text: str) -> str:
    """Normalize text by collapsing whitespace and removing control chars."""
    if not text:
        return ""

    normalized = re.sub(r"[\r\t]+", " ", text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def is_valid_customer_email(sender_value: str) -> bool:
    """Check if email is from a valid customer (not a system email).
    
    Returns False for:
    - no-reply, noreply
    - Google system emails
    - Mailer-daemon
    - Notification systems
    
    Args:
        sender_value: Raw email From header value
    
    Returns:
        True if valid customer email, False if system email
    """
    if not sender_value:
        return False
    
    sender_lower = sender_value.lower()
    
    # Check for system email patterns
    for pattern in SYSTEM_EMAIL_PATTERNS:
        if pattern in sender_lower:
            logger.debug("Skipping system email: %s (matched pattern: %s)", sender_value, pattern)
            return False
    
    return True


def is_email_already_processed(email_id: str) -> bool:
    """Check if email has already been processed.
    
    Args:
        email_id: Gmail message ID
    
    Returns:
        True if already processed, False otherwise
    """
    return email_id in processed_email_ids


def add_to_processed(email_id: str) -> None:
    """Mark email as processed.
    
    Args:
        email_id: Gmail message ID
    """
    processed_email_ids.add(email_id)
    logger.debug("Added email to processed set: %s | Total processed: %d", email_id, len(processed_email_ids))


def load_processed_emails_from_database() -> None:
    """Load replied email IDs from DB into memory for fast duplicate skipping."""
    global processed_email_ids

    try:
        logger.info("Loading processed emails from database...")
        processed_email_ids.update(get_replied_email_ids(limit=5000))
        logger.info("Loaded %d processed emails from database", len(processed_email_ids))
    except Exception as exc:
        logger.exception("Failed to load processed emails from database: %s", exc)


def safe_send_email(email_id: str, customer_email: str, subject: str, body: str) -> dict:
    """Process and send with strict idempotency guards.

    Guard sequence:
    1) Check durable replied state.
    2) Atomically reserve processing state.
    3) Generate+send reply via orchestrator.
    4) Persist final status replied/failed/escalated.
    """
    if check_email_already_replied(email_id):
        logger.info("Skipping email_id=%s (already replied)", email_id)
        return {"status": "skipped", "reason": "already_replied"}

    if not reserve_email_for_processing(email_id):
        logger.info("Skipping email_id=%s (already reserved by another worker)", email_id)
        return {"status": "skipped", "reason": "already_reserved"}

    # Double-check right before send-generation path as strict failsafe.
    if check_email_already_replied(email_id):
        logger.info("Skipping email_id=%s (already replied before send)", email_id)
        update_email_processing_status(email_id, "replied")
        return {"status": "skipped", "reason": "already_replied_before_send"}

    result = handle_customer_email(
        customer_email=customer_email,
        subject=subject,
        body=body,
    )

    final_status = result.get("status", "failed")
    if final_status == "replied":
        update_email_processing_status(email_id, "replied")
        add_to_processed(email_id)
        logger.info("Reply sent successfully for email_id=%s", email_id)
    elif final_status == "escalated":
        update_email_processing_status(email_id, "escalated")
        add_to_processed(email_id)
        logger.info("Email escalated for email_id=%s", email_id)
    else:
        update_email_processing_status(
            email_id,
            "failed",
            last_error=result.get("escalation_reason", "send_or_processing_failed"),
        )
    return result


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

    Ensures each email is processed exactly once by:
    - Tracking processed email IDs
    - Filtering system emails
    - Marking emails as read after processing
    - Loading previous processed emails from database on startup

    When poll_forever is True, this function runs continuously and polls every
    `interval` seconds.
    """
    try:
        ensure_collection()
        refresh_stats = refresh_knowledge_embeddings("data/knowledge")
        logger.info(
            "Knowledge refresh complete: files=%d chunks=%d deleted=%d",
            refresh_stats.get("files", 0),
            refresh_stats.get("chunks", 0),
            refresh_stats.get("deleted", 0),
        )
        create_table_if_not_exists()
        # Load already processed emails from database
        load_processed_emails_from_database()
    except Exception:
        logger.exception("Failed to initialize RAG/DB resources. Aborting pipeline.")
        return

    while True:
        logger.info("Polling Gmail Inbox... (processed so far: %d)", len(processed_email_ids))

        try:
            emails: List[Dict[str, str]] = fetch_unread_emails()
        except Exception:
            logger.exception("Failed to fetch unread emails")
            if not poll_forever:
                return
            time.sleep(interval)
            continue

        if not emails:
            logger.info("No new unread emails")
        else:
            for email in emails:
                message_id = email.get("id", "")
                from_header = email.get("from", "")

                # Skip if already processed
                if is_email_already_processed(message_id):
                    logger.debug("Email already processed, skipping: %s", message_id)
                    continue

                # Durable idempotency check in case Gmail mark-as-read failed.
                if check_email_already_replied(message_id):
                    logger.info("Skipping email_id=%s (already replied)", message_id)
                    add_to_processed(message_id)
                    continue

                # Skip if system email
                if not is_valid_customer_email(from_header):
                    logger.info("Skipping system email from %s (id=%s)", from_header, message_id)
                    try:
                        mark_email_as_read(message_id)
                        logger.debug("Marked system email as read: %s", message_id)
                    except Exception as exc:
                        logger.warning("Could not mark system email as read: %s", exc)
                    add_to_processed(message_id)
                    continue

                try:
                    logger.info("Processing new email: %s from %s", message_id, from_header)
                    
                    # Process email
                    processed = _process_email(email)
                    inserted = insert_email_data(processed)

                    if inserted:
                        logger.info("✓ Email data stored: id=%s", processed.get("id"))
                    else:
                        logger.debug("Email data already in database: id=%s", processed.get("id"))

                    # Extract customer info
                    customer_email = _extract_sender_email(from_header)
                    if not customer_email:
                        logger.warning("Could not parse sender email for id=%s", message_id)
                        add_to_processed(message_id)
                        continue

                    customer_name = extract_customer_name(from_header)
                    subject = processed.get("subject", "")
                    body = processed.get("body", "")

                    logger.info("Processing email from %s: %s", customer_name, subject)
                    
                    # Generate and send with durable idempotency protection.
                    result = safe_send_email(
                        email_id=message_id,
                        customer_email=customer_email,
                        subject=subject,
                        body=body,
                    )

                    if result.get("status") in {"replied", "escalated"}:
                        logger.info(
                            "✓ Reply handled for %s (%s) status=%s email id=%s",
                            customer_email,
                            customer_name,
                            result.get("status"),
                            message_id,
                        )
                    else:
                        logger.error(
                            "✗ Reply failed for %s status=%s email id=%s",
                            customer_email,
                            result.get("status"),
                            message_id,
                        )

                    # Mark email as read
                    if message_id:
                        try:
                            marked = mark_email_as_read(message_id)
                            if marked:
                                logger.info("✓ Marked email as read: %s", message_id)
                            else:
                                logger.warning("Could not mark email as read: %s", message_id)
                        except Exception as exc:
                            logger.exception("Error marking email as read: %s", exc)

                    # Add to processed set for this runtime loop regardless of Gmail mark status.
                    add_to_processed(message_id)
                    logger.info("✓ Email processing complete: %s", message_id)

                except Exception:
                    logger.exception("Failed to process and store email id=%s from %s", message_id, from_header)
                    
                    # Mark as read even if processing failed to avoid infinite retries
                    if message_id:
                        try:
                            marked = mark_email_as_read(message_id)
                            if marked:
                                logger.info("Marked failed email as read to avoid retry: %s", message_id)
                        except Exception:
                            pass
                    
                    # Add to processed to avoid re-processing
                    add_to_processed(message_id)
                    update_email_processing_status(message_id, "failed", last_error="pipeline_exception")

        if not poll_forever:
            return

        logger.debug("Sleeping for %d seconds before next poll...", interval)
        time.sleep(interval)


if __name__ == "__main__":
    run_email_pipeline()

