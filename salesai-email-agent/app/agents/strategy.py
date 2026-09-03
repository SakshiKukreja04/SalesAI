"""Response strategy selection based on intent, emotion, and customer memory."""

from typing import Any, Optional


def select_strategy(intent: str, emotion: str, customer_memory: Optional[Any] = None) -> str:
    """Return a reply strategy label used by the response generator."""
    clean_intent = (intent or "").strip().lower()
    clean_emotion = (emotion or "").strip().lower()

    # Memory-aware strategy overrides
    if customer_memory:
        risk_level = getattr(customer_memory, "risk_level", "LOW")
        repeat_detected = getattr(customer_memory, "repeat_issue_detected", False)
        open_issues = getattr(customer_memory, "open_issues", [])

        if risk_level in {"HIGH", "ESCALATE_IMMEDIATELY"} or repeat_detected or len(open_issues) >= 2:
            return "escalation_prioritized" if risk_level == "ESCALATE_IMMEDIATELY" else "solution_reference"

    if clean_emotion in {"frustrated", "angry", "urgent", "disappointed", "worried"}:
        return "empathetic"
    if clean_intent in {"refund_request", "refund request", "refund_status", "return_request"}:
        return "policy_focused"
    if clean_intent in {"order_status", "order status", "order_tracking", "delayed_delivery", "shipping_inquiry"}:
        return "tracking_focused"
    if clean_intent in {"product_recommendation", "product_inquiry", "product_details"}:
        return "consultative_sales"

    return "general_helpful"
