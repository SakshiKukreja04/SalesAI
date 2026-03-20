"""Intent classification module.

Uses simple keyword heuristics and a Gemini placeholder function so the project
can run now and be upgraded later with real LLM API calls.
"""

from app.config import settings


def _gemini_intent_placeholder(text: str) -> str:
    """Placeholder for Gemini intent classification call."""
    if settings.gemini_api_key:
        # Replace this block with an actual Gemini API request.
        pass

    text_l = text.lower()
    if "refund" in text_l or "return" in text_l:
        return "refund_request"
    if "where" in text_l or "shipping" in text_l or "delivered" in text_l:
        return "shipping_query"
    if "cancel" in text_l:
        return "cancellation_request"
    return "general_support"


def classify_intent(text: str) -> str:
    """Classify customer email intent into a support category."""
    return _gemini_intent_placeholder(text)
