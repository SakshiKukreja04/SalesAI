"""Unit tests for Multimodal Vision Agent & Order-Visual Consistency Guardrail."""

from __future__ import annotations

import unittest
from app.agents.vision_agent import _match_product_with_order_history
from app.memory.memory_models import CustomerMemory, CustomerProfile, VisualContext
from app.memory.memory_formatter import format_customer_memory
from app.rag.query_guard import QueryClass, verify_visual_order_consistency


class TestVisionAgent(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_orders = [
            {
                "order_number": "ORD-1010",
                "status": "shipped",
                "products": [
                    {"name": "ShopiFyX SoundMax Bluetooth Speaker", "sku": "ELX-002", "quantity": 1}
                ],
            },
            {
                "order_number": "ORD-1012",
                "status": "confirmed",
                "products": [
                    {"name": "TravelPro Hard Shell Cabin Case", "sku": "AL-003", "quantity": 1}
                ],
            },
        ]

    def test_order_match_positive_by_sku(self) -> None:
        matched, order_num, pname, sku = _match_product_with_order_history(
            detected_product_name="SoundMax Bluetooth Speaker",
            detected_category="Audio",
            matched_sku="ELX-002",
            customer_orders=self.sample_orders,
        )
        self.assertTrue(matched)
        self.assertEqual(order_num, "ORD-1010")
        self.assertEqual(sku, "ELX-002")

    def test_order_match_positive_by_name(self) -> None:
        matched, order_num, pname, sku = _match_product_with_order_history(
            detected_product_name="Hard Shell Cabin Case",
            detected_category="Luggage",
            matched_sku="UNKNOWN",
            customer_orders=self.sample_orders,
        )
        self.assertTrue(matched)
        self.assertEqual(order_num, "ORD-1012")
        self.assertEqual(sku, "AL-003")

    def test_order_match_positive_by_message_keyword_fallback(self) -> None:
        """Visual detection was Unknown/generic, but customer message mentioned speaker."""
        matched, order_num, pname, sku = _match_product_with_order_history(
            detected_product_name="Unknown",
            detected_category="Other",
            matched_sku="None",
            customer_orders=self.sample_orders,
            customer_message="I received my speaker but it is damaged and broken.",
        )
        self.assertTrue(matched)
        self.assertEqual(order_num, "ORD-1010")
        self.assertEqual(pname, "ShopiFyX SoundMax Bluetooth Speaker")
        self.assertEqual(sku, "ELX-002")

    def test_order_match_negative_unrelated_item(self) -> None:
        """User sends photo of a Crop Top, but orders only contain speaker and suitcase."""
        matched, order_num, pname, sku = _match_product_with_order_history(
            detected_product_name="Floral Printed Crop Top",
            detected_category="Apparel",
            matched_sku="AP-009",
            customer_orders=self.sample_orders,
            customer_message="Here is the picture of the crop top.",
        )
        self.assertFalse(matched)
        self.assertIsNone(order_num)
        self.assertEqual(pname, "Crop Top")

    def test_guardrail_deflects_mismatched_order(self) -> None:
        vc = VisualContext(
            has_images=True,
            image_count=1,
            detected_product_name="Floral Printed Crop Top",
            detected_category="Apparel",
            matched_catalog_sku="AP-009",
            visual_condition="torn",
            matches_order_history=False,
        )
        guard_result = verify_visual_order_consistency(
            visual_context=vc,
            customer_orders=self.sample_orders,
            customer_name="Sakshi Kukreja",
        )
        self.assertIsNotNone(guard_result)
        self.assertEqual(guard_result.classification, QueryClass.ORDER_ITEM_MISMATCH)
        self.assertIn("Floral Printed Crop Top", guard_result.suggested_reply)
        self.assertIn("ORD-1010", guard_result.suggested_reply)
        self.assertIn("ORD-1012", guard_result.suggested_reply)

    def test_guardrail_passes_matched_order(self) -> None:
        vc = VisualContext(
            has_images=True,
            image_count=1,
            detected_product_name="SoundMax Bluetooth Speaker",
            detected_category="Audio",
            matched_catalog_sku="ELX-002",
            visual_condition="damaged",
            matches_order_history=True,
            matched_order_number="ORD-1010",
        )
        guard_result = verify_visual_order_consistency(
            visual_context=vc,
            customer_orders=self.sample_orders,
            customer_name="Sakshi Kukreja",
        )
        self.assertIsNone(guard_result)

    def test_visual_memory_formatting_budget(self) -> None:
        vc = VisualContext(
            has_images=True,
            image_count=1,
            detected_product_name="SoundMax Bluetooth Speaker",
            matched_catalog_sku="ELX-002",
            visual_condition="damaged",
            defect_description="Cracked front grill and scratch",
            matches_order_history=True,
        )
        memory = CustomerMemory(
            profile=CustomerProfile(customer_id="1", email="sakshi@example.com", name="Sakshi"),
            visual_context=vc,
            is_empty=False,
        )
        formatted = format_customer_memory(memory)
        self.assertIn("VISUAL ATTACHMENT EVIDENCE:", formatted.full_context_text)
        self.assertIn("SoundMax Bluetooth Speaker", formatted.full_context_text)
        self.assertIn("ELX-002", formatted.full_context_text)
        self.assertTrue(len(formatted.visual_context_text) <= 250)


if __name__ == "__main__":
    unittest.main()
