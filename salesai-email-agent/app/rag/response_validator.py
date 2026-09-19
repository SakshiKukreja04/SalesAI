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
_WORD_RE = re.compile(r"[a-z0-9-]+")

_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it", "it's",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "should", "shouldn't", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn't", "we", "were", "weren't", "what", "when", "where", "which", "while",
    "who", "whom", "why", "with", "won't", "would", "wouldn't", "you", "your",
    "yours", "yourself", "yourselves", "hi", "hello", "dear", "thanks", "thank"
}

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

_OVERPROMISE_PATTERNS = [
    re.compile(r"\b(?:refund(?:ed)?\s+(?:immediately|right\s+now|today|instantly)|instant(?:ly)?\s+refund|money\s+back\s+today|already\s+processed\s+your\s+refund|refund\s+has\s+(?:already\s+)?been\s+credited)\b", re.IGNORECASE),
    re.compile(r"\b(?:give\s+you\s+a\s+\d+%\s+(?:discount|voucher|coupon)|credited\s+(?:₹|\$|rs\.?)\s*\d+|free\s+gift\s+card|compensation\s+of\s+(?:₹|\$|rs\.?)\s*\d+)\b", re.IGNORECASE),
    re.compile(r"\b(?:guarantee(?:d)?\s+delivery\s+by\s+(?:tomorrow|today)|will\s+(?:definitely|certainly)\s+arrive\s+today)\b", re.IGNORECASE),
    re.compile(r"\b(?:no\s+need\s+to\s+return\s+(?:the\s+)?(?:item|product)|keep\s+the\s+product\s+and\s+(?:we\s+will\s+)?refund|approve\s+(?:the|your)\s+claim\s+without\s+(?:any\s+)?(?:inspection|verification|photos?))\b", re.IGNORECASE),
]

_BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*(?:hi|hello|dear|hey)\b", re.IGNORECASE),
    re.compile(r"\b(?:best\s+regards|sincerely|customer\s+support\s+team|shopifyx\s+team|support\s+specialist)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:thank\s+you\s+for\s+(?:contacting|reaching\s+out)|thanks\s+for\s+(?:contacting|reaching\s+out))\b", re.IGNORECASE),
    re.compile(r"\b(?:please\s+let\s+us\s+know|feel\s+free\s+to|let\s+us\s+know\s+if\s+you\s+have|if\s+you\s+have\s+any\s+(?:other\s+)?questions|reach\s+out\s+if)\b", re.IGNORECASE),
]


@dataclass
class ValidationResult:
    is_valid: bool
    reason: str
    grounded_sentence_count: int
    grounding_ratio: float = 0.0


def _sentences(text: str) -> List[str]:
    stripped = (text or "").strip()
    if not stripped:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(stripped) if s.strip()]


def _content_words(text: str) -> set[str]:
    """Extract substantive non-stopword tokens from text."""
    words = set(_WORD_RE.findall((text or "").lower()))
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def _is_boilerplate_sentence(sentence: str) -> bool:
    """Identify greetings, sign-offs, or standard email framing."""
    s = sentence.strip()
    if not s or len(s) < 15:
        return True
    return any(p.search(s) for p in _BOILERPLATE_PATTERNS)


def _is_sentence_grounded(sentence: str, context_chunks: List[str]) -> bool:
    """Check if sentence has meaningful stopword-filtered overlap with context."""
    sentence_content = _content_words(sentence)
    if not sentence_content:
        return False

    for chunk in context_chunks:
        chunk_content = _content_words(chunk)
        overlap = sentence_content.intersection(chunk_content)
        # Require substantive stopword-free overlap
        if len(overlap) >= 2 or (len(sentence_content) <= 3 and len(overlap) >= 1):
            return True
    return False


def _normalize_timeline_text(text: str) -> str:
    """Normalize timeline expressions (e.g., '3-5 business days' -> '3 to 5 business days')."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r"(\d+)\s*[-–—]\s*(\d+)", r"\1 to \2", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _has_fact_mismatch(answer: str, context_text: str) -> bool:
    answer_facts = [m.group(0).lower() for m in _FACT_RE.finditer(answer or "")]
    if not answer_facts:
        return False

    context_lower = (context_text or "").lower()
    context_norm = _normalize_timeline_text(context_lower)

    for fact in answer_facts:
        fact_norm = _normalize_timeline_text(fact)
        if fact in context_lower or fact_norm in context_norm:
            continue
        fact_without_business = fact_norm.replace("business ", "")
        context_without_business = context_norm.replace("business ", "")
        if fact_without_business in context_without_business:
            continue
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
    """Validate that answer is grounded (>=60% ratio), factual, plain-text, and free of over-promises."""
    if not answer or not answer.strip():
        return ValidationResult(is_valid=False, reason="empty_answer", grounded_sentence_count=0)

    # 1. Check formatting rules & prompt traces
    is_bad_format, format_reason = has_formatting_issues(answer)
    if is_bad_format:
        return ValidationResult(
            is_valid=False,
            reason=format_reason,
            grounded_sentence_count=0,
        )

    # 2. Check for over-promise patterns (instant refund, unverified discounts, etc.)
    for pattern in _OVERPROMISE_PATTERNS:
        if pattern.search(answer):
            return ValidationResult(
                is_valid=False,
                reason="over_promise_detected",
                grounded_sentence_count=0,
            )

    # 3. Verify context exists
    if not context_chunks:
        return ValidationResult(is_valid=False, reason="no_context", grounded_sentence_count=0)

    answer_sentences = _sentences(answer)
    if not answer_sentences:
        return ValidationResult(is_valid=False, reason="empty_answer", grounded_sentence_count=0)

    # 4. Check stopword-filtered grounding on substantive sentences (>=60% grounding ratio)
    substantive_sentences = [s for s in answer_sentences if not _is_boilerplate_sentence(s)]
    if not substantive_sentences:
        substantive_sentences = answer_sentences

    grounded_count = sum(1 for sentence in substantive_sentences if _is_sentence_grounded(sentence, context_chunks))
    grounding_ratio = grounded_count / max(1, len(substantive_sentences))

    if grounding_ratio < 0.60:
        return ValidationResult(
            is_valid=False,
            reason="low_grounding_ratio",
            grounded_sentence_count=grounded_count,
            grounding_ratio=grounding_ratio,
        )

    # 5. Check fact mismatch (numeric timelines / business days)
    context_text = "\n\n".join(context_chunks)
    if _has_fact_mismatch(answer=answer, context_text=context_text):
        return ValidationResult(
            is_valid=False,
            reason="fact_mismatch",
            grounded_sentence_count=grounded_count,
            grounding_ratio=grounding_ratio,
        )

    return ValidationResult(
        is_valid=True,
        reason="ok",
        grounded_sentence_count=grounded_count,
        grounding_ratio=grounding_ratio,
    )
