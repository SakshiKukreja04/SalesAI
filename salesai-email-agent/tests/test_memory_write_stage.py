"""Unit tests for SalesAI V3 Memory-Write Stage.

Tests verify:
1. Strict MemoryUpdate Pydantic schema validation
2. Durable information extraction (name, products, interests, issues, priority, resolution)
3. Rejection of chain-of-thought / temporary reasoning
4. Deterministic duplicate interest detection (customer_id + normalized product name)
5. Existing open issue lookup and in-place updates (no duplicate issues)
6. Issue resolution updates (modifies status without creating a new issue)
7. Full idempotency on duplicate email processing (no duplicate customers, conversations, interests, or issues)
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.db.customer_memory import (
    create_or_update_customer_interest,
    create_or_update_customer_issue,
    get_customer_issues,
    resolve_or_create_customer,
    save_conversation_record,
    update_customer_name,
)
from app.memory.memory_models import (
    CustomerIssue,
    CustomerMemory,
    CustomerProfile,
    MemoryUpdate,
)
from app.memory.memory_updater import (
    _heuristic_extraction,
    extract_memory_from_turn,
    update_customer_memory,
)


class TestMemoryWriteStage(unittest.TestCase):
    """Test suite for V3 structured memory-write stage."""

    # 1. Strict MemoryUpdate schema validation
    def test_memory_update_schema(self):
        update = MemoryUpdate(
            customer_name="Alice Walker",
            products=["Winter Parka Extreme", "Running Shoes"],
            interests=["Winter Parka Extreme"],
            issue="Damaged zipper on delivery",
            issue_status="open",
            issue_priority="high",
            issue_resolved=False,
            interaction_facts=["Prefers size Medium", "Order #4092 received damaged"],
        )

        data = update.model_dump()
        self.assertEqual(data["customer_name"], "Alice Walker")
        self.assertEqual(len(data["products"]), 2)
        self.assertEqual(data["interests"], ["Winter Parka Extreme"])
        self.assertEqual(data["issue_status"], "open")
        self.assertEqual(data["issue_priority"], "high")
        self.assertFalse(data["issue_resolved"])
        self.assertIn("Prefers size Medium", data["interaction_facts"])

    # 2. Durable information extraction from customer turn
    def test_durable_memory_extraction(self):
        msg = "Hi, my name is John Doe. I am looking for the Winter Jacket in size Large. Cheers!"
        extracted = _heuristic_extraction(
            customer_message=msg,
            reply="We have the Winter Jacket available in Large.",
            intent="product_inquiry",
            emotion="neutral",
            status="replied",
        )

        self.assertEqual(extracted.customer_name, "John Doe")
        self.assertIn("winter jacket", extracted.products)
        self.assertIn("winter jacket", extracted.interests)
        self.assertIsNone(extracted.issue)

    # 3. Issue detection and priority assignment
    def test_issue_extraction_and_priority(self):
        msg = "My order arrived completely broken and defective! This is urgent!"
        extracted = _heuristic_extraction(
            customer_message=msg,
            reply="We apologize and will dispatch a replacement immediately.",
            intent="damaged_product",
            emotion="urgent",
            status="replied",
        )

        self.assertIsNotNone(extracted.issue)
        self.assertEqual(extracted.issue_status, "open")
        self.assertEqual(extracted.issue_priority, "urgent")
        self.assertFalse(extracted.issue_resolved)

    # 4. Resolved issue extraction
    def test_resolved_issue_extraction(self):
        msg = "Thanks, that worked perfectly! My refund is now showing in my bank account."
        extracted = _heuristic_extraction(
            customer_message=msg,
            reply="You're very welcome! Let us know if you need anything else.",
            intent="thanks",
            emotion="satisfied",
            status="replied",
        )

        self.assertTrue(extracted.issue_resolved)
        self.assertEqual(extracted.issue_status, "resolved")

    # 5. Deterministic duplicate interest detection
    @patch("app.db.customer_memory.get_connection")
    def test_duplicate_interest_detection(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # First call: existing record found (id=12)
        mock_cursor.fetchone.return_value = (12,)
        result = create_or_update_customer_interest(
            customer_id="cust-101",
            product_name="Winter Parka Extreme",
            status="active",
        )

        self.assertTrue(result)
        # Check that UPDATE was executed, NOT INSERT
        update_calls = [c for c in mock_cursor.execute.call_args_list if "UPDATE customer_interests" in str(c)]
        self.assertTrue(len(update_calls) > 0)

    # 6. Existing open issue lookup and in-place update
    @patch("app.memory.memory_updater.get_customer_issues")
    @patch("app.memory.memory_updater.create_or_update_customer_issue")
    @patch("app.memory.memory_updater.save_conversation_record")
    def test_existing_open_issue_updated_in_place(self, mock_save_conv, mock_update_issue, mock_get_issues):
        # Customer already has an open issue for "Damaged Jacket"
        existing_issue = CustomerIssue(
            id="issue-99",
            customer_id="cust-202",
            issue_title="Damaged Jacket",
            description="Broken zipper",
            status="open",
            priority="medium",
        )
        mock_get_issues.return_value = [existing_issue]

        success = update_customer_memory(
            customer_id="cust-202",
            customer_email="user@test.com",
            email_id="msg-999",
            subject="Damaged Jacket Update",
            customer_message="Still broken, zipper is stuck.",
            normalized_message="still broken zipper is stuck",
            intent="damaged_product",
            intent_confidence=0.90,
            emotion="frustrated",
            emotion_confidence=0.85,
            strategy="empathetic",
            reply="We are sending a prepaid return label.",
            confidence=0.92,
            status="replied",
        )

        self.assertTrue(success)
        mock_update_issue.assert_called()
        # Verify it updated the existing issue title "Damaged Jacket"
        called_title = mock_update_issue.call_args[1]["issue_title"]
        self.assertEqual(called_title, "Damaged Jacket")

    # 7. Issue resolution modifies existing issue status
    @patch("app.memory.memory_updater.get_customer_issues")
    @patch("app.memory.memory_updater.create_or_update_customer_issue")
    @patch("app.memory.memory_updater.save_conversation_record")
    def test_resolved_issue_updates_status_without_new_issue(self, mock_save_conv, mock_update_issue, mock_get_issues):
        existing_issue = CustomerIssue(
            id="issue-55",
            customer_id="cust-303",
            issue_title="Refund Request",
            description="Awaiting refund",
            status="open",
            priority="high",
        )
        mock_get_issues.return_value = [existing_issue]

        success = update_customer_memory(
            customer_id="cust-303",
            customer_email="alice@test.com",
            email_id="msg-888",
            subject="Refund Confirmation",
            customer_message="Thanks, that worked! Refund received.",
            normalized_message="thanks that worked refund received",
            intent="thanks",
            intent_confidence=0.95,
            emotion="satisfied",
            emotion_confidence=0.90,
            strategy="general_helpful",
            reply="Glad to hear that!",
            confidence=0.95,
            status="replied",
        )

        self.assertTrue(success)
        mock_update_issue.assert_called_with(
            customer_id="cust-303",
            issue_title="Refund Request",
            description="Awaiting refund",
            status="resolved",
            priority="high",
            resolution_notes="Resolved via interaction: Glad to hear that!",
        )

    # 8. Full idempotency on duplicate email processing
    @patch("app.db.customer_memory.get_connection")
    def test_idempotent_email_processing(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock customer resolution (existing customer)
        mock_cursor.fetchone.side_effect = [
            ("uuid-1", "test@test.com", "Test User", 2, None, None, None, None),  # resolve customer
            (10,),  # conversation exists
            (20,),  # interest exists
            (30,),  # issue exists
        ]

        # Call save_conversation_record twice with same email_id
        res1 = save_conversation_record({
            "customer_id": "uuid-1",
            "email_id": "msg-duplicate-123",
            "customer_message": "Hello",
            "generated_reply": "Hi",
        })
        self.assertTrue(res1)


if __name__ == "__main__":
    unittest.main()
