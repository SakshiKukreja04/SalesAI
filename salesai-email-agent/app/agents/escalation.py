"""Email escalation module for high-risk customer issues.

Handles automatic escalation of low-confidence replies and urgent issues
to human support team.
"""

import logging
from datetime import datetime, timezone
from typing import Dict

from app.email.send_email import send_email


LOGGER = logging.getLogger(__name__)

ESCALATION_EMAIL = "support@shopifyx.com"


def escalate_to_human(
    customer_email: str,
    subject: str,
    body: str,
    reason: str,
    generated_reply: str = "",
    confidence_score: float = 0.0,
) -> bool:
    """Send escalation ticket to support team.
    
    Args:
        customer_email: Customer's email address
        subject: Original email subject
        body: Original email body
        reason: Reason for escalation (e.g., "low_confidence", "angry_complaint")
        generated_reply: AI-generated reply for reference
        confidence_score: Confidence score of the generated reply
    
    Returns:
        True if escalation email sent, False otherwise
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        
        escalation_body = f"""
ESCALATION ALERT - {timestamp}
{'='*60}

Customer Email: {customer_email}
Original Subject: {subject}
Escalation Reason: {reason}
Confidence Score: {confidence_score:.2f}

ORIGINAL CUSTOMER MESSAGE:
{'-'*60}
{body}

AI-GENERATED REPLY (for reference):
{'-'*60}
{generated_reply if generated_reply else "(No reply generated)"}

{'='*60}
Action Required: Please review this customer message and provide
a manual response if necessary.
"""
        
        success = send_email(
            to_email=ESCALATION_EMAIL,
            subject=f"[ESCALATION] {subject}",
            body=escalation_body,
        )
        
        if success:
            LOGGER.info(
                "Escalation sent successfully (email=%s, reason=%s, confidence=%f)",
                customer_email,
                reason,
                confidence_score,
            )
        else:
            LOGGER.error(
                "Failed to send escalation (email=%s, reason=%s)",
                customer_email,
                reason,
            )
        
        return success
        
    except Exception as exc:
        LOGGER.error("Escalation error: %s", exc)
        return False


def should_escalate(
    confidence_score: float,
    intent: str,
    emotion: str,
) -> tuple[bool, str]:
    """Determine if email should be escalated to human support.
    
    Args:
        confidence_score: AI-generated confidence (0.0 - 1.0)
        intent: Classified intent
        emotion: Detected emotion
    
    Returns:
        Tuple of (should_escalate: bool, reason: str)
    """
    if confidence_score < 0.6:
        return True, f"low_confidence ({confidence_score:.2f})"
    
    if intent == "complaint" and emotion == "angry":
        return True, "angry_complaint"
    
    if emotion in {"urgent", "very_angry", "furious"}:
        return True, f"high_emotion ({emotion})"
    
    return False, ""
