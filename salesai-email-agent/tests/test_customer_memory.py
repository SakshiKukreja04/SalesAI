"""Comprehensive unit tests for SalesAI V3 Customer Memory Agent.

Tests cover all 15 required test scenarios:
1. Existing customer resolution
2. New customer creation
3. Email normalization
4. Recent memory retrieval
5. Open issue retrieval
6. Interest retrieval
7. Similar interaction retrieval
8. Empty customer history
9. Memory retrieval failure
10. Duplicate interest prevention
11. Duplicate issue prevention
12. Conversation idempotency
13. Memory update failure after email send
14. Response generation with memory
15. Response generation without memory
"""

from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock, patch

from app.db.customer_memory import (
    create_or_update_customer_interest,
    create_or_update_customer_issue,
    get_customer_conversations,
    get_customer_interests,
    get_customer_issues,
    normalize_email,
    resolve_or_create_customer,
    save_conversation_record,
)
from app.memory.customer_memory import memory_agent
from app.memory.memory_formatter import format_customer_memory
from app.memory.memory_models import (
    ConversationRecord,
    CustomerInterest,
    CustomerIssue,
    CustomerMemory,
    CustomerProfile,
    FormattedMemoryContext,
)
from app.memory.memory_retriever import retrieve_customer_memory
from app.memory.memory_updater import (
    _heuristic_extraction,
    extract_memory_from_turn,
    update_customer_memory,
)
from app.prompts.response_prompt import build_response_prompt


class TestCustomerMemoryV3(unittest.TestCase):
    """Test suite covering all V3 Customer Memory specifications."""

    # 1. Existing customer resolution
    @patch("app.db.customer_memory.get_connection")
    def test_existing_customer_resolution(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        now = datetime.now(timezone.utc)
        # Simulate existing customer record: id=42, email, name, total_interactions=3
        mock_cursor.fetchone.return_value = ("42", "jane@example.com", "Jane Doe", 3, now, now, now, now)

        profile = resolve_or_create_customer("jane@example.com", name="Jane Doe")

        self.assertEqual(profile.customer_id, "42")
        self.assertEqual(profile.email, "jane@example.com")
        self.assertEqual(profile.total_interactions, 4)
        mock_cursor.execute.assert_called()

    # 2. New customer creation
    @patch("app.db.customer_memory.get_connection")
    def test_new_customer_creation(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Simulate customer not found on lookup, then returning new ID 99 on insert
        mock_cursor.fetchone.side_effect = [None, ("99",)]

        profile = resolve_or_create_customer("newuser@example.com", name="New Customer")

        self.assertEqual(profile.customer_id, "99")
        self.assertEqual(profile.email, "newuser@example.com")
        self.assertEqual(profile.total_interactions, 1)

    # 3. Email normalization
    def test_email_normalization(self):
        # Case insensitivity
        self.assertEqual(normalize_email("User.Name@Example.COM"), "user.name@example.com")
        # Whitespace stripping
        self.assertEqual(normalize_email("   test@domain.com  \n"), "test@domain.com")
        # Display name extraction
        self.assertEqual(normalize_email("John Doe <john.doe@company.org>"), "john.doe@company.org")
        self.assertEqual(normalize_email("  \"Jane Smith\" <JANE@TEST.NET>  "), "jane@test.net")
        # Empty input
        self.assertEqual(normalize_email(""), "")

    # 4. Recent memory retrieval
    @patch("app.db.customer_memory.get_connection")
    def test_recent_memory_retrieval(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        now = datetime.now(timezone.utc)
        # Mock conversations rows
        mock_cursor.fetchall.return_value = [
            ("1", "10", "msg-1", "Refund", "Where is my refund?", "where is my refund",
             "refund_request", 0.9, "frustrated", 0.8, "policy_focused",
             "We are reviewing your refund.", 0.85, "replied", "", "gemini", 2, 1, now, now)
        ]

        conversations = get_customer_conversations(customer_id="10", limit=5)
        self.assertEqual(len(conversations), 1)
        self.assertEqual(conversations[0].intent, "refund_request")
        self.assertEqual(conversations[0].emotion, "frustrated")

    # 5. Open issue retrieval
    @patch("app.db.customer_memory.get_connection")
    def test_open_issue_retrieval(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            ("101", "15", "Defective Jacket", "Zipper is broken", "open", "high", now, now)
        ]

        open_issues = get_customer_issues(customer_id="15", status="open")
        self.assertEqual(len(open_issues), 1)
        self.assertEqual(open_issues[0].issue_title, "Defective Jacket")
        self.assertEqual(open_issues[0].status, "open")
        self.assertEqual(open_issues[0].priority, "high")

    # 6. Interest retrieval
    @patch("app.db.customer_memory.get_connection")
    def test_interest_retrieval(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        now = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            ("1", "20", "Winter Parka", "active", now, now),
            ("2", "20", "Trail Running Shoes", "active", now, now),
        ]

        interests = get_customer_interests(customer_id="20", status="active")
        self.assertEqual(len(interests), 2)
        self.assertEqual(interests[0].product_name, "Winter Parka")
        self.assertEqual(interests[1].product_name, "Trail Running Shoes")

    # 7. Similar interaction retrieval
    @patch("app.rag.chroma_store.ensure_user_collection")
    def test_similar_interaction_retrieval(self, mock_ensure_col):
        mock_col = MagicMock()
        mock_col.query.return_value = {
            "documents": [["I received a damaged jacket last month."]],
            "metadatas": [[{"intent": "damaged_product", "emotion": "disappointed", "timestamp": "2026-08-01"}]],
        }
        mock_ensure_col.return_value = mock_col

        from app.memory.memory_retriever import _retrieve_semantic_interactions
        interactions = _retrieve_semantic_interactions("customer@example.com", "jacket problem", k=2)

        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0]["intent"], "damaged_product")
        self.assertIn("damaged jacket", interactions[0]["message"])

    # 8. Empty customer history
    @patch("app.db.customer_memory.get_customer_by_id")
    @patch("app.db.customer_memory.get_customer_conversations")
    @patch("app.db.customer_memory.get_customer_issues")
    @patch("app.db.customer_memory.get_customer_interests")
    @patch("app.memory.memory_retriever._retrieve_semantic_interactions")
    @patch("app.memory.memory_retriever._retrieve_relevant_previous_replies")
    def test_empty_customer_history(self, mock_replies, mock_semantic, mock_interests, mock_issues, mock_convs, mock_prof):
        mock_prof.return_value = CustomerProfile(customer_id="5", email="new@example.com", name="New User", total_interactions=1)
        mock_convs.return_value = []
        mock_issues.return_value = []
        mock_interests.return_value = []
        mock_semantic.return_value = []
        mock_replies.return_value = []

        memory = retrieve_customer_memory(customer_id="5", customer_email="new@example.com")

        self.assertEqual(len(memory.recent_conversations), 0)
        self.assertEqual(len(memory.open_issues), 0)
        self.assertEqual(memory.risk_level, "LOW")

    # 9. Memory retrieval failure resilience
    @patch("app.db.customer_memory.resolve_or_create_customer", side_effect=Exception("Database connection timeout"))
    @patch("app.db.customer_memory.get_customer_by_id", side_effect=Exception("Database connection timeout"))
    @patch("app.db.customer_memory.get_customer_conversations", side_effect=Exception("Database connection timeout"))
    def test_memory_retrieval_failure(self, mock_convs, mock_by_id, mock_resolve):
        # Must not raise exception, but return fallback CustomerMemory
        memory = retrieve_customer_memory(customer_id="99", customer_email="fail@example.com")

        self.assertIsNotNone(memory)
        self.assertEqual(memory.risk_level, "LOW")
        self.assertEqual(len(memory.recent_conversations), 0)

    # 10. Duplicate interest prevention
    @patch("app.db.customer_memory.get_connection")
    def test_duplicate_interest_prevention(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Simulate interest already exists (id=5)
        mock_cursor.fetchone.return_value = ("5",)

        success = create_or_update_customer_interest(customer_id="30", product_name="Winter Jacket", status="active")
        self.assertTrue(success)

        # Ensure it executed UPDATE rather than duplicate INSERT
        call_sql = mock_cursor.execute.call_args_list[-1][0][0]
        self.assertIn("UPDATE customer_interests", call_sql)

    # 11. Duplicate issue prevention
    @patch("app.db.customer_memory.get_connection")
    def test_duplicate_issue_prevention(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Simulate matching open issue already exists (id=12)
        mock_cursor.fetchone.return_value = ("12", "open")

        issue_id = create_or_update_customer_issue(
            customer_id="30",
            issue_title="Refund Request",
            description="Still waiting for refund",
            status="open",
            resolution_notes="Followup inquiry",
        )

        self.assertEqual(issue_id, "12")
        call_sql = mock_cursor.execute.call_args_list[-1][0][0]
        self.assertIn("UPDATE customer_issues", call_sql)

    # 12. Conversation idempotency
    @patch("app.db.customer_memory.get_connection")
    def test_conversation_idempotency(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Simulate conversation with email_id="msg-12345" already exists (id=77)
        mock_cursor.fetchone.return_value = ("77",)

        record = {
            "customer_id": "50",
            "email_id": "msg-12345",
            "subject": "Inquiry",
            "customer_message": "Hello",
            "status": "replied",
        }

        saved = save_conversation_record(record)
        self.assertTrue(saved)
        call_sql = mock_cursor.execute.call_args_list[-1][0][0]
        self.assertIn("UPDATE conversations", call_sql)

    # 13. Memory update failure resilience after email send
    @patch("app.memory.memory_updater.extract_memory_from_turn", side_effect=Exception("Extraction timeout"))
    def test_memory_update_failure_after_email_send(self, mock_extract):
        # Must return False, log error, and not raise exception
        success = update_customer_memory(
            customer_id="1",
            customer_email="test@example.com",
            email_id="msg-99",
            subject="Test",
            customer_message="Message",
            normalized_message="message",
            intent="inquiry",
            intent_confidence=0.9,
            emotion="neutral",
            emotion_confidence=0.9,
            strategy="general_helpful",
            reply="Reply text",
            confidence=0.9,
            status="replied",
        )
        self.assertFalse(success)

    # 14. Response generation with memory
    def test_response_generation_with_memory(self):
        memory = CustomerMemory(
            profile=CustomerProfile(customer_id="10", email="vip@example.com", name="Alice Smith", total_interactions=5),
            open_issues=[
                CustomerIssue(id="1", customer_id="10", issue_title="Refund Request #102", status="open", priority="high")
            ],
            interests=[CustomerInterest(id="1", customer_id="10", product_name="Winter Jacket", interest_status="active")],
            is_empty=False,
        )

        formatted = format_customer_memory(memory, current_intent="refund_request", current_message="Where is my refund?")

        self.assertIn("CUSTOMER PROFILE:", formatted.full_context_text)
        self.assertIn("Alice Smith", formatted.full_context_text)
        self.assertIn("Refund Request #102", formatted.full_context_text)
        self.assertIn("Winter Jacket", formatted.full_context_text)

        prompt = build_response_prompt(
            customer_message="Where is my refund?",
            intent="refund_request",
            intent_confidence=0.95,
            emotion="frustrated",
            emotion_intensity=0.8,
            context_chunks=["Refunds take 5-7 business days."],
            customer_memory_context=formatted.full_context_text,
            strategy="policy_focused",
        )

        self.assertIn("CUSTOMER MEMORY CONTEXT:", prompt)
        self.assertIn("Refund Request #102", prompt)
        self.assertIn("Knowledge-base policy ALWAYS has priority over customer memory", prompt)

    # 15. Response generation without memory (clean fallback)
    def test_response_generation_without_memory(self):
        empty_memory = CustomerMemory(is_empty=True)
        formatted = format_customer_memory(empty_memory)

        self.assertIn("[NEW CUSTOMER", formatted.full_context_text)

        prompt = build_response_prompt(
            customer_message="What are your shipping hours?",
            intent="shipping_inquiry",
            intent_confidence=0.90,
            emotion="neutral",
            emotion_intensity=0.3,
            context_chunks=["We ship Monday through Friday."],
            customer_memory_context="",
            strategy="general_helpful",
        )

        self.assertNotIn("CUSTOMER MEMORY CONTEXT:", prompt)
        self.assertIn("CUSTOMER MESSAGE:", prompt)
        self.assertIn("We ship Monday through Friday.", prompt)


if __name__ == "__main__":
    unittest.main()
