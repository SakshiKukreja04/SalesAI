"""Unit tests for SalesAI V3 Response Generation Prompt and Generator.

Tests verify:
1. Customer memory improves continuity
2. KB policy overrides stale memory
3. Previous replies are not blindly copied
4. Sensitive/internal memory is never exposed
5. Angry customers receive empathetic responses
6. Unresolved issues are acknowledged
7. Resolved issues are not incorrectly reopened
8. Structured JSON output contract
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.agents.generator import (
    _fallback_reply,
    generate_reply,
    generate_reply_structured,
    sanitize_customer_reply,
)
from app.memory.memory_models import (
    ConversationRecord,
    CustomerInterest,
    CustomerIssue,
    CustomerMemory,
    CustomerProfile,
)
from app.prompts.response_prompt import build_response_prompt
from app.rag.response_validator import validate_response


class TestResponseGenerationV3(unittest.TestCase):
    """Test suite for V3 response generation prompt hierarchy and rules."""

    # 1. Customer memory improves continuity
    def test_customer_memory_improves_continuity(self):
        memory = CustomerMemory(
            profile=CustomerProfile(customer_id="101", email="sarah@test.com", name="Sarah Connor", total_interactions=3),
            open_issues=[
                CustomerIssue(id="1", customer_id="101", issue_title="Order #90210 delivery delay", status="open", priority="high")
            ],
            is_empty=False,
        )

        prompt = build_response_prompt(
            customer_message="Any news on my package?",
            intent="delayed_delivery",
            intent_confidence=0.92,
            emotion="worried",
            emotion_intensity=0.75,
            context_chunks=["Standard shipping takes 3-5 business days. Delivery delays are tracked via Order ID."],
            customer_memory_context="Customer Name: Sarah Connor\nOpen Issue: Order #90210 delivery delay",
            strategy="tracking_focused",
        )

        self.assertIn("Sarah Connor", prompt)
        self.assertIn("Order #90210", prompt)
        self.assertIn("Avoid asking for information the customer has already provided", prompt)

    # 2. KB policy overrides stale memory
    def test_kb_policy_overrides_stale_memory(self):
        # Memory contains an outdated claim, but KB policy is authoritative
        stale_memory_context = "Customer claims they were previously told returns are accepted within 30 days."
        current_kb_context = ["ShopiFyX strictly accepts returns within 7 days of delivery in original packaging."]

        prompt = build_response_prompt(
            customer_message="I bought this 18 days ago, I want to return it.",
            intent="return_request",
            intent_confidence=0.95,
            emotion="neutral",
            emotion_intensity=0.5,
            context_chunks=current_kb_context,
            customer_memory_context=stale_memory_context,
            strategy="policy_focused",
        )

        self.assertIn("Current ShopiFyX KB policy ALWAYS overrides older conversation statements", prompt)
        self.assertIn("ShopiFyX strictly accepts returns within 7 days", prompt)

    # 3. Previous replies are not blindly copied
    def test_previous_replies_are_not_blindly_copied(self):
        prompt = build_response_prompt(
            customer_message="Can I exchange for a larger size?",
            intent="exchange_request",
            intent_confidence=0.88,
            emotion="neutral",
            emotion_intensity=0.4,
            context_chunks=["Exchanges are permitted within 7 days for size variations."],
            history="Thanks for contacting us about a return. We will process your return shortly.",
            customer_memory_context="",
            strategy="general_helpful",
        )

        self.assertIn("do NOT blindly duplicate", prompt)
        self.assertIn("4. PREVIOUS AI REPLIES", prompt)

    # 4. Sensitive/internal memory is never exposed
    def test_sensitive_internal_memory_never_exposed(self):
        prompt = build_response_prompt(
            customer_message="Help me with my shoes",
            intent="product_inquiry",
            intent_confidence=0.9,
            emotion="neutral",
            emotion_intensity=0.5,
            context_chunks=["Running shoes are in stock."],
            customer_memory_context="Internal UUID: efdd9be0-101a-4080-bf83-3d9fb9e5d119\nRisk Score: 0.85",
            strategy="general_helpful",
        )

        self.assertIn("Never expose internal/sensitive memory details", prompt)
        self.assertIn("Do not mention 'memory', 'database', 'customer profile'", prompt)

    # 5. Angry customers receive empathetic responses
    def test_angry_customers_receive_empathetic_responses(self):
        fallback = _fallback_reply(
            strategy="empathetic",
            intent="refund_request",
            emotion="angry",
            context_docs=["Refunds take 5-7 business days to be credited to the original payment method."],
        )

        self.assertIn("understand your frustration", fallback.lower())
        self.assertIn("apologize for the inconvenience", fallback.lower())

    # 6. Unresolved issues are acknowledged
    def test_unresolved_issues_are_acknowledged(self):
        memory = CustomerMemory(
            open_issues=[
                CustomerIssue(id="1", customer_id="101", issue_title="Defective Jacket Zipper", status="open", priority="high")
            ],
            is_empty=False,
        )

        fallback = _fallback_reply(
            strategy="general_helpful",
            intent="damaged_product",
            emotion="frustrated",
            context_docs=["Replacements for damaged items are shipped within 48 hours."],
            customer_memory=memory,
        )

        self.assertIn("Defective Jacket Zipper", fallback)
        self.assertIn("actively tracking", fallback)

    # 7. Resolved issues are not incorrectly reopened
    def test_resolved_issues_are_not_incorrectly_reopened(self):
        prompt = build_response_prompt(
            customer_message="I have a question about new jacket styles.",
            intent="product_inquiry",
            intent_confidence=0.92,
            emotion="happy",
            emotion_intensity=0.8,
            context_chunks=["New winter jackets arrive every Tuesday."],
            customer_memory_context="Resolved Issues: [RESOLVED] Refund for broken zipper",
            strategy="consultative_sales",
        )

        self.assertIn("Do NOT reopen issues that are already resolved", prompt)

    # 8. Structured JSON output contract parsing and validation
    def test_structured_json_output_parsing(self):
        raw_json = (
            '{\n'
            '  "reply": "Thank you for contacting us. Your refund is processed in 5-7 business days.",\n'
            '  "confidence": 0.94,\n'
            '  "requires_escalation": false,\n'
            '  "escalation_reason": null\n'
            '}'
        )

        cleaned = sanitize_customer_reply(raw_json)
        self.assertIn("Thank you for contacting us. Your refund is processed in 5-7 business days.", cleaned)
        self.assertTrue(cleaned.startswith("Hi,"))
        self.assertTrue(cleaned.endswith("Best regards,\nCustomer Support Team\nShopiFyX"))

        # Ensure validator passes on the extracted reply
        validation = validate_response(
            answer=cleaned,
            context_chunks=["Eligible refunds are processed in 5-7 business days."],
        )
        self.assertTrue(validation.is_valid)


if __name__ == "__main__":
    unittest.main()
