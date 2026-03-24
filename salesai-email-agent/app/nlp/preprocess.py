"""Text preprocessing utilities for incoming customer emails."""

import re


_SIGNATURE_RE = re.compile(
    r"(thanks(?: and regards)?|best regards|regards|sincerely|cheers|sent from my|warm regards)\b[\s\S]*$",
    re.IGNORECASE,
)
_GREETING_RE = re.compile(r"^(hi|hello|hey|dear team|dear support|team)[^\n.!?]*[\n.!?]\s*", re.IGNORECASE)
_QUESTION_SENTENCE_RE = re.compile(r"[^.!?]*\?", re.IGNORECASE)


def preprocess_text(text: str) -> str:
    """Clean email text with lightweight normalization steps."""
    lowered = text.lower().strip()
    lowered = re.sub(r"\s+", " ", lowered)
    cleaned = re.sub(r"[^a-z0-9\s.,!?-]", "", lowered)
    return cleaned


def clean_query_text(text: str) -> str:
    """Clean inbound email text for retrieval embedding/querying.

    Steps:
    - remove trailing signatures
    - remove common greeting prefix
    - select strongest intent sentence (prefer question)
    """
    original = (text or "").strip()
    if not original:
        return ""

    without_signature = _SIGNATURE_RE.sub("", original).strip()
    without_greeting = _GREETING_RE.sub("", without_signature).strip()

    question_matches = _QUESTION_SENTENCE_RE.findall(without_greeting)
    if question_matches:
        candidate = max(question_matches, key=lambda q: len(q.strip()))
        return preprocess_text(candidate)

    sentences = re.split(r"(?<=[.!?])\s+", without_greeting)
    sentences = [s.strip() for s in sentences if s.strip()]
    if sentences:
        candidate = max(sentences, key=lambda s: len(s))
        return preprocess_text(candidate)

    return preprocess_text(without_greeting)
