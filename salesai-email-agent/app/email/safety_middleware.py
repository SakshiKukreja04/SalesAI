"""Safety middleware for outbound customer replies."""

import logging
from typing import List, Tuple

from app.rag.response_validator import SAFE_FALLBACK_RESPONSE, validate_response


LOGGER = logging.getLogger(__name__)


def enforce_email_safety(
    answer: str,
    retrieved_context_chunks: List[str],
    is_conversational_or_guarded: bool = False,
) -> Tuple[str, bool, str]:
    """Block ungrounded replies and return a safe fallback when needed.

    Returns:
        (final_answer, blocked, reason)
    """
    if is_conversational_or_guarded:
        if not answer or not answer.strip():
            return SAFE_FALLBACK_RESPONSE, True, "empty_answer"
        return answer, False, "ok"

    validation = validate_response(answer=answer, context_chunks=retrieved_context_chunks)
    if validation.is_valid:
        return answer, False, "ok"

    LOGGER.warning(
        "SMTP safety blocked answer (reason=%s grounded_sentences=%d)",
        validation.reason,
        validation.grounded_sentence_count,
    )
    return SAFE_FALLBACK_RESPONSE, True, validation.reason
