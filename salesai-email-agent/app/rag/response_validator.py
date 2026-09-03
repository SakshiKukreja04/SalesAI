"""Post-generation fact checking and grounding validation."""

from dataclasses import dataclass
import re
from typing import List


SAFE_FALLBACK_RESPONSE = (
    "Hi,\n\n"
    "Thank you for contacting ShopiFyX.\n\n"
    "We are currently reviewing your request with our support team to provide you with the most accurate assistance. A support specialist will follow up with you shortly.\n\n"
    "Best regards,\n"
    "Customer Support Team\n"
    "ShopiFyX"
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_FACT_RE = re.compile(
    r"\b(\d+\s*(?:-|to)\s*\d+\s*(?:business\s+)?days|\d+\s*(?:business\s+)?days)\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[a-z0-9]+")

_DISALLOWED_PATTERNS = [
    (re.compile(r"\*\*[^*]+\*\*"), "markdown_bold"),
    (re.compile(r"__[^_]+__"), "markdown_bold"),
    (re.compile(r"^#{1,6}\s+", re.MULTILINE), "markdown_heading"),
    (re.compile(r"^\s*[-*•+]\s+", re.MULTILINE), "markdown_bullet"),
    (re.compile(r"^\s*\d+\.\s+", re.MULTILINE), "numbered_list"),
    (re.compile(r"```"), "code_block"),
    (re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE), "markdown_table"),
]

_PROMPT_TRACE_PATTERNS = [
    re.compile(r"\buser query\s*:", re.IGNORECASE),
    re.compile(r"\brole\s*:", re.IGNORECASE),
    re.compile(r"\bconstraint\s+\d", re.IGNORECASE),
    re.compile(r"\bself-correction", re.IGNORECASE),
    re.compile(r"\bconfidence score\s*:", re.IGNORECASE),
    re.compile(r"here is (?:the|your|a) (?:response|email|reply)", re.IGNORECASE),
    re.compile(r"\bnext steps\s*:\s*none\b", re.IGNORECASE),
]


@dataclass
class ValidationResult:
    is_valid: bool
    reason: str
    grounded_sentence_count: int


def _sentences(text: str) -> List[str]:
    stripped = (text or "").strip()
    if not stripped:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(stripped) if s.strip()]


def _word_set(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def _is_sentence_grounded(sentence: str, context_chunks: List[str]) -> bool:
    sentence_words = _word_set(sentence)
    if len(sentence_words) < 3:
        return False

    for chunk in context_chunks:
        overlap = sentence_words.intersection(_word_set(chunk))
        # Require substantive overlap to avoid weak lexical matches.
        if len(overlap) >= 4:
            return True
    return False


def _has_fact_mismatch(answer: str, context_text: str) -> bool:
    answer_facts = [m.group(0).lower() for m in _FACT_RE.finditer(answer or "")]
    if not answer_facts:
        return False

    context_lower = (context_text or "").lower()
    for fact in answer_facts:
        if fact not in context_lower:
            return True
    return False


def has_formatting_issues(answer: str) -> tuple[bool, str]:
    """Check for unwanted markdown formatting or prompt traces."""
    if not answer:
        return True, "empty_answer"

    for pattern, reason in _DISALLOWED_PATTERNS:
        if pattern.search(answer):
            return True, f"format_{reason}"

    for trace_pattern in _PROMPT_TRACE_PATTERNS:
        if trace_pattern.search(answer):
            return True, "format_prompt_trace"

    return False, "ok"


def validate_response(answer: str, context_chunks: List[str]) -> ValidationResult:
    """Validate that answer is grounded, factual, and strictly follows plain-text rules."""
    if not answer or not answer.strip():
        return ValidationResult(is_valid=False, reason="empty_answer", grounded_sentence_count=0)

    # Check formatting rules
    is_bad_format, format_reason = has_formatting_issues(answer)
    if is_bad_format:
        return ValidationResult(
            is_valid=False,
            reason=format_reason,
            grounded_sentence_count=0,
        )

    if not context_chunks:
        return ValidationResult(is_valid=False, reason="no_context", grounded_sentence_count=0)

    answer_sentences = _sentences(answer)
    if not answer_sentences:
        return ValidationResult(is_valid=False, reason="empty_answer", grounded_sentence_count=0)

    grounded_count = sum(1 for sentence in answer_sentences if _is_sentence_grounded(sentence, context_chunks))
    if grounded_count < 1:
        return ValidationResult(
            is_valid=False,
            reason="not_grounded",
            grounded_sentence_count=grounded_count,
        )

    context_text = "\n\n".join(context_chunks)
    if _has_fact_mismatch(answer=answer, context_text=context_text):
        return ValidationResult(
            is_valid=False,
            reason="fact_mismatch",
            grounded_sentence_count=grounded_count,
        )

    return ValidationResult(is_valid=True, reason="ok", grounded_sentence_count=grounded_count)
