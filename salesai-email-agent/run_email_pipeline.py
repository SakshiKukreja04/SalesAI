"""Step-1 execution script for SalesAI Email Agent.

This script demonstrates:
- Fetching unread emails from Gmail
- Cleaning and normalizing message text
- Extracting key fields
- Printing structured console output for demo
"""

import re
import time
from typing import Dict, List

from app.email.fetch_emails import fetch_unread_emails


def clean_text(text: str) -> str:
    """Normalize text by collapsing whitespace and removing control chars."""
    if not text:
        return ""

    normalized = re.sub(r"[\r\t]+", " ", text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _print_email(email: Dict[str, str]) -> None:
    """Print one email using a clear demo-friendly format."""
    email_id = email.get("id", "N/A")
    sender = email.get("from", "N/A")
    subject = email.get("subject", "(No Subject)")
    timestamp = email.get("timestamp", "N/A")

    body = clean_text(email.get("body", ""))
    if not body:
        body = "[No readable body content]"

    print("-" * 40)
    print("EMAIL RECEIVED")
    print("-" * 40)
    print(f"ID: {email_id}")
    print(f"FROM: {sender}")
    print(f"SUBJECT: {subject}")
    print(f"TIME: {timestamp}")
    print()
    print("BODY:")
    print(body)
    print()
    print("-" * 40)


def run_email_pipeline(interval: int = 30, poll_forever: bool = False) -> None:
    """Fetch unread emails and print extracted, cleaned output to console.

    When poll_forever is True, this function runs continuously and polls every
    `interval` seconds.
    """
    while True:
        print("Polling Gmail Inbox...")

        emails: List[Dict[str, str]] = fetch_unread_emails()

        if not emails:
            print("No new emails")
        else:
            for email in emails:
                _print_email(email)

        if not poll_forever:
            return

        time.sleep(interval)


if __name__ == "__main__":
    run_email_pipeline()
