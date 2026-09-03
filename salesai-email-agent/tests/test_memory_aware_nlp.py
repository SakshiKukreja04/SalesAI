"""Unit tests for Memory-Aware Intent and Emotion Detection (SalesAI V3).

Tests verify:
1. Standalone message (current message priority)
2. Follow-up message
3. Ambiguous message (disambiguated via memory)
4. Continuation of refund issue ("Still waiting for it.")
5. Continuation of order issue ("Still waiting for it.")
6. Continuation of product inquiry ("Can I get the same one?")
7. Emotional state changing between messages (no automatic carry-over)
"""

from __future__ import annotations

import unittest
from app.memory.memory_models import (
    ConversationRecord,
    CustomerInterest,
    CustomerIssue,
    CustomerMemory,
    CustomerProfile,
)
from app.nlp.memory_nlp_classifier import (
    _heuristic_nlp_disambiguation,
    classify_intent_and_emotion_with_memory,
)


class TestMemoryAwareNLP(unittest.TestCase):
    """Test suite for memory-assisted intent and emotion classification."""

    # 1. Standalone message: current message priority must override historical memory
    def test_standalone_message_priority(self):
        # Customer has an open refund issue in history, but currently asks about warranty
        memory = CustomerMemory(
            profile=CustomerProfile(customer_id="101", email="user@test.com", total_interactions=4),
            open_issues=[
                CustomerIssue(id="1", customer_id="101", issue_title="Refund Request for Shoes", status="open", priority="high")
            ],
            recent_conversations=[
                ConversationRecord(intent="refund_request", emotion="angry", customer_message="I demand my refund!")
            ],
            is_empty=False,
        )

        result = _heuristic_nlp_disambiguation(
            message="What is the warranty policy on the leather jacket?",
            customer_memory=memory,
        )

        # Current message is clearly a warranty inquiry, NOT a refund
        self.assertIn(result.intent, {"warranty_inquiry", "warranty_claim"})
        self.assertEqual(result.emotion, "neutral")
        self.assertFalse(result.memory_used)
        self.assertIn("warranty", result.reasoning_summary.lower())

    # 2. Follow-up message: resolves reference when message is continuation
    def test_follow_up_message_resolution(self):
        memory = CustomerMemory(
            profile=CustomerProfile(customer_id="102", email="user@test.com"),
            open_issues=[
                CustomerIssue(id="2", customer_id="102", issue_title="Damaged Zipper on Jacket", status="open", priority="high")
            ],
            is_empty=False,
        )

        result = _heuristic_nlp_disambiguation(
            message="Same issue again with the zipper.",
            customer_memory=memory,
        )

        self.assertEqual(result.intent, "damaged_product")
        self.assertTrue(result.memory_used)
        self.assertIn("open issue", result.reasoning_summary.lower())

    # 3. Ambiguous message: disambiguates short prompt via memory
    def test_ambiguous_message_disambiguation(self):
        memory = CustomerMemory(
            profile=CustomerProfile(customer_id="103", email="user@test.com"),
            open_issues=[
                CustomerIssue(id="3", customer_id="103", issue_title="Delivery Delay #442", status="open", priority="medium")
            ],
            is_empty=False,
        )

        result = _heuristic_nlp_disambiguation(
            message="Any update on this?",
            customer_memory=memory,
        )

        self.assertEqual(result.intent, "delayed_delivery")
        self.assertTrue(result.memory_used)

    # 4. Continuation of refund issue ("Still waiting for it.")
    def test_continuation_of_refund_issue(self):
        memory = CustomerMemory(
            profile=CustomerProfile(customer_id="104", email="user@test.com"),
            open_issues=[
                CustomerIssue(id="4", customer_id="104", issue_title="Refund Request #992", status="open", priority="high")
            ],
            is_empty=False,
        )

        result = _heuristic_nlp_disambiguation(
            message="Still waiting for it.",
            customer_memory=memory,
        )

        self.assertEqual(result.intent, "refund_status")
        self.assertEqual(result.emotion, "frustrated")
        self.assertTrue(result.memory_used)
        self.assertIn("refund", result.reasoning_summary.lower())

    # 5. Continuation of order issue ("Still waiting for it.")
    def test_continuation_of_order_issue(self):
        memory = CustomerMemory(
            profile=CustomerProfile(customer_id="105", email="user@test.com"),
            open_issues=[
                CustomerIssue(id="5", customer_id="105", issue_title="Order Delivery Issue #881", status="open", priority="medium")
            ],
            is_empty=False,
        )

        result = _heuristic_nlp_disambiguation(
            message="Still waiting for it.",
            customer_memory=memory,
        )

        self.assertEqual(result.intent, "delayed_delivery")
        self.assertEqual(result.emotion, "frustrated")
        self.assertTrue(result.memory_used)
        self.assertIn("delivery", result.reasoning_summary.lower())

    # 6. Continuation of product inquiry ("Can I get the same one?")
    def test_continuation_of_product_inquiry(self):
        memory = CustomerMemory(
            profile=CustomerProfile(customer_id="106", email="user@test.com"),
            interests=[
                CustomerInterest(id="1", customer_id="106", product_name="Winter Parka Extreme", interest_status="active")
            ],
            is_empty=False,
        )

        result = _heuristic_nlp_disambiguation(
            message="Can I get the same one?",
            customer_memory=memory,
        )

        self.assertEqual(result.intent, "product_inquiry")
        self.assertTrue(result.memory_used)
        self.assertIn("Winter Parka Extreme", result.reasoning_summary)

    # 7. Emotional state changing between messages (no automatic carryover of past anger)
    def test_emotional_state_changing_between_messages(self):
        # Customer was furious in past turns, but the current message is satisfied
        memory = CustomerMemory(
            profile=CustomerProfile(customer_id="107", email="user@test.com", total_interactions=6),
            open_issues=[],
            recent_conversations=[
                ConversationRecord(intent="complaint", emotion="angry", customer_message="This is completely unacceptable!")
            ],
            risk_level="HIGH",
            is_empty=False,
        )

        result = _heuristic_nlp_disambiguation(
            message="Thanks, that worked perfectly! Appreciate the help.",
            customer_memory=memory,
        )

        # Current emotion must be happy / satisfied, NOT angry!
        self.assertIn(result.emotion, {"happy", "satisfied"})
        self.assertEqual(result.intent, "thanks")
        self.assertNotEqual(result.emotion, "angry")

    # 8. Complete structured dictionary response schema verification
    def test_structured_response_contract(self):
        memory = CustomerMemory(is_empty=True)
        result = classify_intent_and_emotion_with_memory(
            message="Hello, do you have running shoes in size 10?",
            customer_memory=memory,
        )

        self.assertIn("intent", result)
        self.assertIn("intent_confidence", result)
        self.assertIn("emotion", result)
        self.assertIn("emotion_confidence", result)
        self.assertIn("reasoning_summary", result)
        self.assertIn("memory_used", result)

        self.assertIsInstance(result["intent"], str)
        self.assertIsInstance(result["intent_confidence"], float)
        self.assertIsInstance(result["emotion"], str)
        self.assertIsInstance(result["emotion_confidence"], float)
        self.assertIsInstance(result["reasoning_summary"], str)
        self.assertIsInstance(result["memory_used"], bool)


if __name__ == "__main__":
    unittest.main()
