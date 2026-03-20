"""Gmail unread email fetching module for SalesAI.

Features:
- OAuth2 flow with automatic token generation and refresh
- Unread email retrieval using Gmail API
- MIME parsing with text/plain preference and text/html fallback
- Safe base64 URL decoding
- Polling helper for periodic inbox checks
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import html
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


load_dotenv()

LOGGER = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", os.getenv("GMAIL_CREDENTIALS_PATH", ""))
GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", os.getenv("GMAIL_TOKEN_PATH", ""))
GOOGLE_OAUTH_HOST = os.getenv("GOOGLE_OAUTH_HOST", "localhost")
GOOGLE_OAUTH_PORT = int(os.getenv("GOOGLE_OAUTH_PORT", "8080"))


def _decode_base64_urlsafe(data: str) -> str:
    """Decode Gmail base64-url-safe content into UTF-8 text safely."""
    if not data:
        return ""

    try:
        padding = "=" * (-len(data) % 4)
        decoded_bytes = base64.urlsafe_b64decode(data + padding)
        return decoded_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        LOGGER.warning("Failed to decode base64 content: %s", exc)
        return ""


def clean_html(raw_html: str) -> str:
    """Remove HTML tags and normalize spaces for readable plain text."""
    if not raw_html:
        return ""

    no_scripts = re.sub(r"<script.*?>.*?</script>", " ", raw_html, flags=re.IGNORECASE | re.DOTALL)
    no_styles = re.sub(r"<style.*?>.*?</style>", " ", no_scripts, flags=re.IGNORECASE | re.DOTALL)
    no_tags = re.sub(r"<[^>]+>", " ", no_styles)
    unescaped = html.unescape(no_tags)
    return re.sub(r"\s+", " ", unescaped).strip()


def extract_headers(payload: Dict[str, Any]) -> Dict[str, str]:
    """Extract common email headers from Gmail payload."""
    headers = payload.get("headers", []) if payload else []
    extracted = {"from": "", "subject": "", "date": ""}

    for header in headers:
        name = header.get("name", "").strip().lower()
        value = header.get("value", "").strip()

        if name == "from":
            extracted["from"] = value
        elif name == "subject":
            extracted["subject"] = value
        elif name == "date":
            extracted["date"] = value

    return extracted


def _collect_text_parts(parts: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    """Recursively collect plain and HTML text parts from MIME structure."""
    plain_parts: List[str] = []
    html_parts: List[str] = []

    for part in parts:
        mime_type = part.get("mimeType", "")
        body_data = (part.get("body") or {}).get("data", "")

        if mime_type == "text/plain" and body_data:
            plain_parts.append(_decode_base64_urlsafe(body_data))
        elif mime_type == "text/html" and body_data:
            html_parts.append(clean_html(_decode_base64_urlsafe(body_data)))

        child_parts = part.get("parts", [])
        if child_parts:
            child_plain, child_html = _collect_text_parts(child_parts)
            plain_parts.extend(child_plain)
            html_parts.extend(child_html)

    return plain_parts, html_parts


def extract_body(payload: Dict[str, Any]) -> str:
    """Extract message body from Gmail payload.

    Preference order:
    1) text/plain
    2) text/html (cleaned)
    """
    if not payload:
        return ""

    mime_type = payload.get("mimeType", "")
    body_data = (payload.get("body") or {}).get("data", "")
    parts = payload.get("parts", [])

    if parts:
        plain_parts, html_parts = _collect_text_parts(parts)
        if plain_parts:
            return "\n".join(p for p in plain_parts if p).strip()
        if html_parts:
            return "\n".join(p for p in html_parts if p).strip()

    if mime_type == "text/html" and body_data:
        return clean_html(_decode_base64_urlsafe(body_data))

    if body_data:
        return _decode_base64_urlsafe(body_data).strip()

    return ""


def _internal_date_to_iso(internal_date_ms: str) -> str:
    """Convert Gmail internalDate milliseconds string into ISO timestamp."""
    try:
        dt = datetime.fromtimestamp(int(internal_date_ms) / 1000.0, tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return ""


def get_gmail_service() -> Optional[Any]:
    """Create and return an authenticated Gmail API service client.

    Behavior:
    - If token exists, load and refresh when possible.
    - If token does not exist or is invalid, run OAuth login flow.
    - Save generated token for future runs.
    """
    if not GOOGLE_CREDENTIALS_PATH or not GOOGLE_TOKEN_PATH:
        LOGGER.error(
            "Missing env vars GOOGLE_CREDENTIALS_PATH or GOOGLE_TOKEN_PATH. "
            "Please configure them in .env"
        )
        return None

    creds: Optional[Credentials] = None

    try:
        if os.path.exists(GOOGLE_TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_PATH, SCOPES)

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                LOGGER.info("Gmail OAuth token refreshed successfully.")
            except Exception as exc:
                LOGGER.warning("Token refresh failed, re-running OAuth flow: %s", exc)
                creds = None

        if not creds or not creds.valid:
            if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
                LOGGER.error("Credentials file not found at %s", GOOGLE_CREDENTIALS_PATH)
                return None

            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(host=GOOGLE_OAUTH_HOST, port=GOOGLE_OAUTH_PORT)

            with open(GOOGLE_TOKEN_PATH, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())
            LOGGER.info("Generated new Gmail token at %s", GOOGLE_TOKEN_PATH)

        return build("gmail", "v1", credentials=creds)

    except Exception as exc:
        LOGGER.exception("Failed to create Gmail service: %s", exc)
        return None


def fetch_unread_emails(max_results: int = 20) -> List[Dict[str, str]]:
    """Fetch unread emails from Gmail and return normalized dictionaries."""
    service = get_gmail_service()
    if service is None:
        return []

    emails: List[Dict[str, str]] = []

    try:
        response = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["UNREAD"], maxResults=max_results)
            .execute()
        )
        message_refs = response.get("messages", [])

        if not message_refs:
            LOGGER.info("No unread emails found.")
            return []

        for ref in message_refs:
            message_id = ref.get("id", "")
            if not message_id:
                continue

            try:
                message = (
                    service.users()
                    .messages()
                    .get(userId="me", id=message_id, format="full")
                    .execute()
                )

                payload = message.get("payload") or {}
                headers = extract_headers(payload)
                body = extract_body(payload) or message.get("snippet", "")
                timestamp = headers.get("date") or _internal_date_to_iso(message.get("internalDate", ""))

                emails.append(
                    {
                        "id": message_id,
                        "from": headers.get("from", ""),
                        "subject": headers.get("subject", ""),
                        "body": body,
                        "timestamp": timestamp,
                    }
                )
            except HttpError as exc:
                LOGGER.error("Failed to fetch message %s: %s", message_id, exc)
            except Exception as exc:
                LOGGER.exception("Unexpected error while parsing message %s: %s", message_id, exc)

        return emails

    except HttpError as exc:
        LOGGER.error("Gmail API error while listing unread emails: %s", exc)
        return []
    except Exception as exc:
        LOGGER.exception("Unexpected error while fetching unread emails: %s", exc)
        return []


def poll_emails(interval: int = 30) -> None:
    """Continuously poll unread emails at a fixed interval in seconds."""
    LOGGER.info("Starting email poller with interval=%s seconds", interval)
    seen_ids: set[str] = set()

    while True:
        try:
            emails = fetch_unread_emails()
            for email in emails:
                message_id = email.get("id", "")
                if message_id and message_id not in seen_ids:
                    LOGGER.info(
                        "New unread email | id=%s | from=%s | subject=%s",
                        message_id,
                        email.get("from", ""),
                        email.get("subject", ""),
                    )
                    seen_ids.add(message_id)
        except Exception as exc:
            LOGGER.exception("Error in email polling loop: %s", exc)

        time.sleep(interval)


def poll_gmail_inbox(max_results: int = 20) -> List[Dict[str, str]]:
    """Backward-compatible wrapper used by the existing FastAPI endpoint."""
    return fetch_unread_emails(max_results=max_results)
