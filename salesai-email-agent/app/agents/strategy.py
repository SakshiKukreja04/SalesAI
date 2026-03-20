"""Response strategy selection based on intent and emotion."""


def select_strategy(intent: str, emotion: str) -> str:
    """Return a reply strategy label used by the response generator."""
    if emotion in {"frustrated", "angry", "urgent"}:
        return "empathetic"
    if intent == "Refund Request":
        return "policy_focused"
    if intent == "Order Status":
        return "tracking_focused"
    return "general_helpful"
