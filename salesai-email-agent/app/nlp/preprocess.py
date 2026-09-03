"""Text preprocessing utilities for incoming customer emails."""

from __future__ import annotations

import re


_SIGNATURE_RE = re.compile(
    r"\n\s*(?:best regards|warm regards|kind regards|regards|sincerely|cheers|thanks\s*(?:and|&)\s*regards|sent from my)\b[\s\S]*$",
    re.IGNORECASE,
)
_TRAILING_SIGN_OFF_RE = re.compile(
    r"\n\s*(?:best|thanks|thank you),?\s*\n\s*[a-zA-Z\s]{1,30}$",
    re.IGNORECASE,
)
_GREETING_RE = re.compile(r"^(?:hi|hello|hey|dear team|dear support|team)[^\n.!?]*[\n,!?]\s*", re.IGNORECASE)


def strip_email_history(text: str) -> str:
    """Strip quoted reply chains and previous email history from customer messages."""
    if not text:
        return ""

    cleaned = text
    # 1. Match "On <date>, <sender> wrote:" or similar thread starters
    on_wrote_match = re.search(r"\bOn\s+[A-Za-z0-9,\s.:<>/@_-]+?(?:wrote|said):\s*", cleaned, re.IGNORECASE)
    if on_wrote_match:
        cleaned = cleaned[:on_wrote_match.start()]


    # 2. Match "--- Original Message ---" or "-----Original Message-----"
    orig_msg_match = re.search(r"(?:^|\n)\s*-{2,}\s*Original Message\s*-{2,}", cleaned, re.IGNORECASE)
    if orig_msg_match:
        cleaned = cleaned[:orig_msg_match.start()]

    # 3. Match "From: ... Sent: ... Subject:" headers
    from_header_match = re.search(r"(?:^|\n)\s*From:\s*.*?\n\s*(?:Sent|Date):\s*", cleaned, re.IGNORECASE)
    if from_header_match:
        cleaned = cleaned[:from_header_match.start()]

    # 4. Remove quoted lines starting with '>'
    lines = []
    for line in cleaned.splitlines():
        if line.strip().startswith(">"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)

    return cleaned.strip()


def preprocess_text(text: str) -> str:
    """Clean email text with thread stripping and normalization steps."""
    unquoted = strip_email_history(text)
    if not unquoted:
        unquoted = text or ""
    lowered = unquoted.lower().strip()
    lowered = re.sub(r"\s+", " ", lowered)
    cleaned = re.sub(r"[^a-z0-9\s.,!?-]", "", lowered)
    return cleaned


def clean_query_text(text: str) -> str:
    """Clean inbound email text for retrieval embedding/querying.

    Steps:
    - strip email history and quotes
    - remove trailing sign-offs and footers
    - remove leading greeting prefix
    - return clean normalized text containing all questions and sentences
    """
    original = strip_email_history((text or "").strip())
    if not original:
        original = (text or "").strip()

    without_signature = _SIGNATURE_RE.sub("", original)
    without_signature = _TRAILING_SIGN_OFF_RE.sub("", without_signature).strip()
    without_greeting = _GREETING_RE.sub("", without_signature).strip()

    if not without_greeting:
        return preprocess_text(original)

    return preprocess_text(without_greeting)

