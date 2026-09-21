"""Unit tests for Inventory Action Execution and Vectra Defect Triage."""

from __future__ import annotations

import unittest
from app.tools.inventory_tool import (
    check_inventory_availability,
    execute_refund_action,
    execute_exchange_action,
)
from app.memory.memory_models import CustomerIssue, VisualContext, CustomerMemory, CustomerProfile
from app.memory.memory_formatter import format_customer_memory


class TestInventoryActionEngine(unittest.TestCase):
    def test_inventory_check_in_stock(self) -> None:
        res = check_inventory_availability(sku="FW-009", product_name="ShopiFyX AeroStride Running Shoes")
        self.assertTrue(res.in_stock)
        self.assertGreater(res.available_units, 0)
        self.assertEqual(res.category, "Footwear")

    def test_inventory_check_out_of_stock_with_alternatives(self) -> None:
        res = check_inventory_availability(sku="ELX-002", product_name="ShopiFyX SoundMax Bluetooth Speaker")
        self.assertFalse(res.in_stock)
        self.assertEqual(res.available_units, 0)
        self.assertGreater(len(res.alternative_products), 0)
        # Should recommend other audio products like ELX-003 or ELX-001
        alt_skus = [a["sku"] for a in res.alternative_products]
        self.assertTrue("ELX-003" in alt_skus or "ELX-001" in alt_skus)

    def test_execute_refund_action(self) -> None:
        res = execute_refund_action(
            order_number="ORD-5501",
            customer_email="sakshi@example.com",
            amount=89.99,
            reason="Delaminated shoe outsole defect",
        )
        self.assertEqual(res["status"], "refund_initiated")
        self.assertTrue(res["refund_id"].startswith("REF-"))
        self.assertEqual(res["order_number"], "ORD-5501")

    def test_execute_exchange_action(self) -> None:
        res = execute_exchange_action(
            order_number="ORD-1010",
            customer_email="sakshi@example.com",
            sku="FW-009",
            replacement_sku="FW-009",
            reason="Damaged sole replacement",
        )
        self.assertEqual(res["status"], "exchange_pending")
        self.assertTrue(res["exchange_id"].startswith("EX-"))

    def test_vectra_visual_context_formatting(self) -> None:
        vc = VisualContext(
            has_images=True,
            image_count=1,
            detected_product_name="AeroStride Running Shoes",
            matched_catalog_sku="FW-009",
            visual_condition="damaged",
            defect_type="sole_delamination",
            severity_level="severe_unusable",
            defect_area_ratio=0.35,
            diagnostic_reasoning="Outsole rubber tread has separated from the midsole at the heel.",
            matches_order_history=True,
            matched_order_number="ORD-5501",
        )
        mem = CustomerMemory(
            profile=CustomerProfile(customer_id="cust-1", email="sakshi@example.com", name="Sakshi"),
            visual_context=vc,
            is_empty=False,
        )
        formatted = format_customer_memory(mem)
        self.assertIn("sole_delamination", formatted.full_context_text)
        self.assertIn("severe_unusable", formatted.full_context_text)
        self.assertIn("0.35", formatted.full_context_text)
        self.assertIn("ORD-5501", formatted.full_context_text)


if __name__ == "__main__":
    unittest.main()
