"""Response strategy selection based on intent and emotion."""


def select_strategy(intent: str, emotion: str) -> str:
    """Return a reply strategy label used by the response generator."""
    if emotion == "negative":
        return "empathetic"
    if intent == "refund_request":
        return "policy_focused"
    if intent == "shipping_query":
        return "tracking_focused"
    return "general_helpful"
