import unittest
from unittest.mock import MagicMock, patch

from app.neo4j_retrieval import format_graph_context, get_customer_context, get_salesai_context


class Neo4jRetrievalTest(unittest.TestCase):
    def test_unknown_customer_returns_empty_context(self):
        with patch("app.neo4j_retrieval.neo4j_client") as client:
            client.configured = True
            client.read_records.return_value = []

            result = get_salesai_context("unknown@example.com")

        self.assertFalse(result["customer_found"])
        self.assertEqual(result["orders"], [])

    def test_customer_orders_and_relationship_properties_are_formatted(self):
        row = {
            "customer_id": "c-1",
            "customer_name": "Sakshi",
            "customer_email": "sakshi@example.com",
            "customer_tier": "gold",
            "customer_status": "active",
            "order_id": "o-1",
            "order_number": "SFX-100",
            "order_status": "shipped",
            "order_date": "2026-09-01",
            "total_amount": 1799,
            "product_name": "TechNova Power Bank",
            "sku": "P008",
            "quantity": 1,
            "unit_price": 1799,
            "shipment_status": "in_transit",
            "shipped_at": "2026-09-02",
            "tracking_number": "TRK-1",
            "estimated_delivery": "2026-09-05",
            "delivered_at": None,
        }
        with patch("app.neo4j_retrieval.neo4j_client") as client:
            client.configured = True
            client.read_records.return_value = [row]

            context = get_customer_context("SAKSHI@example.com")
            formatted = format_graph_context({
                **context,
                "previous_conversations": [],
                "issues": [],
                "interests": [],
            })

        self.assertTrue(context["customer_found"])
        self.assertEqual(context["orders"][0]["products"][0]["quantity"], 1)
        self.assertIn("Order SFX-100", formatted)
        self.assertIn("order date=2026-09-01", formatted)
        self.assertIn("shipped at=2026-09-02", formatted)
        self.assertIn("tracking=TRK-1", formatted)


if __name__ == "__main__":
    unittest.main()