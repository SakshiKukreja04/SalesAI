"""End-to-End Multi-Turn Test for Multimodal Defect Triage, Inventory Action & Supabase Issues."""

from __future__ import annotations

import unittest
from unittest.mock import patch
from app.agents.orchestrator import handle_customer_email
from app.memory.memory_models import CustomerMemory, CustomerProfile, VisualContext
from app.db.customer_memory import get_all_customer_issues, get_customer_issues


class TestEndToEndMultimodalSupabaseFlow(unittest.TestCase):
    def setUp(self) -> None:
        self.test_email = "test.shoecustomer@shopifyx.in"
        self.test_customer_id = "test-cust-9988"

    def test_turn1_and_turn2_end_to_end_flow(self) -> None:
        print("\n" + "=" * 70)
        print("--- STEP 1: Turn 1 - Customer Reports Damaged Shoe Sole (Image Attached) ---")
        print("=" * 70)

        # Mock image data
        sample_attachments = [
            {
                "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "mime_type": "image/png",
            }
        ]

        # Mock visual analysis output returning damaged sole
        mock_vc = VisualContext(
            has_images=True,
            image_count=1,
            detected_product_name="ShopiFyX AeroStride Running Shoes",
            detected_category="Footwear",
            matched_catalog_sku="FW-009",
            is_catalog_product=True,
            visual_condition="damaged",
            defect_type="sole_delamination",
            severity_level="severe_unusable",
            defect_area_ratio=0.35,
            diagnostic_reasoning="Outsole rubber tread has separated from the EVA midsole near the heel.",
            defect_description="Sole delamination near heel",
            visual_confidence=0.95,
            summary="Customer provided image of AeroStride Running Shoes showing sole delamination.",
            matches_order_history=True,
            matched_order_number="ORD-5501",
        )

        with patch("app.agents.vision_agent.analyze_email_images", return_value=mock_vc), \
             patch("app.agents.orchestrator.send_email", return_value=True):
            turn1_response = handle_customer_email(
                customer_email=self.test_email,
                subject="Damaged Shoe Sole on Order ORD-5501",
                body="I received my AeroStride shoes 2 days ago and the sole is already peeling off and damaged. See attached picture. What can I do?",
                attachments=sample_attachments,
            )

        print("\n[Turn 1 Agent Response Output]:")
        print(turn1_response.get("reply"))

        # Assertions for Turn 1
        reply_text = turn1_response.get("reply", "")
        self.assertIn("Full Refund", reply_text)
        self.assertIn("Replacement", reply_text)
        self.assertIn("ORD-5501", reply_text)

        print("\n" + "=" * 70)
        print("--- STEP 2: Turn 2 - Customer Selects 100% Full Refund ---")
        print("=" * 70)

        with patch("app.agents.orchestrator.send_email", return_value=True):
            turn2_response = handle_customer_email(
                customer_email=self.test_email,
                subject="Re: Damaged Shoe Sole on Order ORD-5501",
                body="Thank you. I prefer to get a full refund for this order please.",
            )

        print("\n[Turn 2 Agent Response Output]:")
        print(turn2_response.get("reply"))

        # Assertions for Turn 2
        reply_text_2 = turn2_response.get("reply", "")
        self.assertIn("refund", reply_text_2.lower())
        self.assertIn("REF-", reply_text_2)
        self.assertIn("ORD-5501", reply_text_2)
        print("\n[E2E Verification Complete]: Multi-turn defect triage & action mutation successfully executed!")

    def test_dar_zero_no_defect_escalates_to_human(self) -> None:
        """When attachment has DAR=0 / no defect found, notify customer and escalate to human team."""
        sample_attachments = [
            {
                "data": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "mime_type": "image/png",
            }
        ]

        # Mock visual analysis returning no defect / DAR 0
        mock_vc = VisualContext(
            has_images=True,
            image_count=1,
            detected_product_name="DeskMate Adjustable Laptop Stand",
            detected_category="Accessories",
            matched_catalog_sku="AL-012",
            is_catalog_product=True,
            visual_condition="unclear",
            defect_type="none",
            severity_level="none",
            defect_area_ratio=0.0,
            diagnostic_reasoning="No visible physical damage or fracture detected on the product surface.",
            defect_description="",
            visual_confidence=0.85,
            summary="Customer provided image of laptop stand with no apparent defects.",
            matches_order_history=True,
            matched_order_number="ORD-1005",
        )

        with patch("app.agents.vision_agent.analyze_email_images", return_value=mock_vc), \
             patch("app.agents.orchestrator.send_email", return_value=True), \
             patch("app.agents.orchestrator.escalate_to_human") as mock_escalate:
            response = handle_customer_email(
                customer_email="vanshika@example.com",
                subject="Received defective product",
                body="Hey just received my laptop stand for ord-1005 but the received product seems to be defective... let me know what can i do",
                attachments=sample_attachments,
            )

            reply = response.get("reply", "")
            # Ensure it does NOT offer automated refund/replacement claim of verified damage
            self.assertNotIn("verified the damage", reply.lower())
            # Ensure it tells the customer no visible defect was detected & case is forwarded to human support
            self.assertIn("no visible physical defect", reply.lower())
            self.assertIn("human customer support", reply.lower())
            self.assertIn("ORD-1005", reply)

            # Ensure escalation to human function was called
            mock_escalate.assert_called_once()


if __name__ == "__main__":
    unittest.main()

