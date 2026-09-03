"""Response validation and email decision logic for SalesAI V3 with Customer Memory awareness."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.prompts.response_prompt import build_email_decision_prompt
from app.rag.response_validator import validate_response


UNSUPPORTED_PATTERNS = [
    r"I have completed",
    r"I already processed",
    r"refund has been issued",
    r"we will definitely ship",
    r"guaranteed refund",
    r"100% approved",
]


def _contains_unsupported_claim(answer: str) -> bool:
    text = (answer or "").lower()
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in UNSUPPORTED_PATTERNS)


def validate_email_response(answer: str, context_chunks: List[str], intent: str, emotion: str) -> Dict[str, Any]:
    """Run the V3 validation step before any send decision."""
    validation = validate_response(answer=answer, context_chunks=context_chunks)

    issues: List[str] = []
    if not validation.is_valid:
        issues.append(validation.reason)
    if not answer or not answer.strip():
        issues.append("empty_answer")
    if _contains_unsupported_claim(answer):
        issues.append("unsupported_claim")
    if "I do not know" in answer and not context_chunks:
        issues.append("missing_context")
    grounded = validation.is_valid and not issues

    return {
        "grounded": bool(grounded),
        "valid": bool(grounded),
        "confidence": 0.93 if grounded else 0.41,
        "issues": issues,
        "intent": intent,
        "emotion": emotion,
    }


def decide_email_action(
    intent_confidence: float,
    emotion_confidence: float,
    validation: Dict[str, Any],
    intent: str,
    emotion: str,
    customer_message: str = "",
    generated_response: str = "",
    retrieved_context: List[str] | None = None,
    customer_risk_level: str = "LOW",
    customer_memory: Optional[Any] = None,
) -> Dict[str, Any]:
    """Return the backend-controlled decision for a generated reply, accounting for customer risk."""
    risk_level = customer_risk_level
    if customer_memory and hasattr(customer_memory, "risk_level"):
        risk_level = customer_memory.risk_level

    decision_prompt = build_email_decision_prompt(
        customer_message=customer_message or "",
        intent=intent,
        intent_confidence=float(intent_confidence or 0.0),
        emotion=emotion,
        emotion_intensity=float(emotion_confidence or 0.0),
        generated_response=generated_response or "",
        retrieved_context=retrieved_context or [],
        customer_risk_level=risk_level,
    )
    validation["decision_prompt"] = decision_prompt

    # 1. Immediate escalation checks
    if risk_level == "ESCALATE_IMMEDIATELY":
        return {
            "decision": "HUMAN_REVIEW",
            "confidence": 0.85,
            "reason": "Customer risk level requires immediate human escalation.",
            "requires_human": True,
        }

    # 2. Check for repeat unresolved issues from customer memory
    if customer_memory:
        open_issues = getattr(customer_memory, "open_issues", [])
        repeat_detected = getattr(customer_memory, "repeat_issue_detected", False)
        if len(open_issues) >= 2 and repeat_detected:
            return {
                "decision": "HUMAN_REVIEW",
                "confidence": 0.82,
                "reason": "Customer has multiple repeat unresolved issues.",
                "requires_human": True,
            }

    # 3. Dynamic Thresholds based on customer risk
    intent_threshold = 0.82 if risk_level == "HIGH" else 0.75
    emotion_threshold = 0.75 if risk_level == "HIGH" else 0.65

    if (
        validation.get("valid")
        and validation.get("grounded")
        and intent_confidence >= intent_threshold
        and emotion_confidence >= emotion_threshold
        and not validation.get("issues")
    ):
        return {
            "decision": "AUTO_SEND",
            "confidence": 0.91,
            "reason": "Response is grounded, validated, and meets the confidence threshold.",
            "requires_human": False,
        }

    if intent_confidence < intent_threshold or emotion_confidence < emotion_threshold or validation.get("issues"):
        return {
            "decision": "HUMAN_REVIEW",
            "confidence": 0.74,
            "reason": "The response is not confident enough, high risk, or validation indicates uncertainty.",
            "requires_human": True,
        }

    return {
        "decision": "DO_NOT_SEND",
        "confidence": 0.67,
        "reason": "The response is unsafe or unsupported for automated sending.",
        "requires_human": True,
    }


def build_final_email(customer_name: str, original_message: str, intent: str, emotion: str, approved_response: str) -> Dict[str, str]:
    """Build a minimal final email JSON from the approved response."""
    subject = f"Update on your {intent.replace('_', ' ').title()} request"
    body = (approved_response or "Thank you for your message. We will review this shortly.").strip()
    if customer_name and customer_name.strip():
        body = f"Hi {customer_name},\n\n{body}"
    return {"subject": subject, "body": body}
