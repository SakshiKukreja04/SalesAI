"""Inventory & Action Execution Tool for SalesAI Customer Support Agent.

Inspired by ECom-Bench and Tau-Bench:
Provides deterministic stock checking, alternative product discovery,
and autonomous mutation execution (refunds, exchanges, issue tracking).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

LOGGER = logging.getLogger(__name__)

# Default catalog inventory fallback when live WMS is mocked or offline
DEFAULT_CATALOG_INVENTORY: Dict[str, Dict[str, Any]] = {
    "FW-009": {"name": "ShopiFyX AeroStride Running Shoes", "stock": 14, "category": "Footwear", "price": 89.99},
    "FW-001": {"name": "ShopiFyX Urban Runner Sneakers", "stock": 22, "category": "Footwear", "price": 79.99},
    "ELX-002": {"name": "ShopiFyX SoundMax Bluetooth Speaker", "stock": 0, "category": "Audio", "price": 69.99},  # OOS test case
    "ELX-003": {"name": "ShopiFyX SoundMax Pro Portable Speaker", "stock": 18, "category": "Audio", "price": 84.99},
    "ELX-001": {"name": "ShopiFyX NoiseCancelling Headphones", "stock": 9, "category": "Audio", "price": 129.99},
    "AL-003": {"name": "TravelPro Hard Shell Cabin Case", "stock": 8, "category": "Luggage", "price": 119.99},
    "AL-001": {"name": "VenturePro 40L Cabin Backpack", "stock": 15, "category": "Luggage", "price": 89.99},
    "HK-001": {"name": "AeroFry 4L Digital Air Fryer", "stock": 5, "category": "Kitchenware", "price": 99.99},
}


@dataclass
class InventoryResult:
    """Result of inventory stock availability inquiry."""

    sku: str
    product_name: str
    in_stock: bool
    available_units: int
    category: str = "General"
    warehouse_location: str = "WH-CENTRAL-01"
    unit_price: float = 0.0
    alternative_products: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sku": self.sku,
            "product_name": self.product_name,
            "in_stock": self.in_stock,
            "available_units": self.available_units,
            "category": self.category,
            "warehouse_location": self.warehouse_location,
            "unit_price": self.unit_price,
            "alternative_products": self.alternative_products,
        }


def check_inventory_availability(
    sku: Optional[str] = None,
    product_name: Optional[str] = None,
) -> InventoryResult:
    """Check stock availability for a SKU or product name and suggest alternatives if out of stock."""
    clean_sku = (sku or "").strip().upper()
    clean_name = (product_name or "").strip().lower()

    # 1. Match by SKU
    matched_entry = None
    resolved_sku = clean_sku

    if clean_sku and clean_sku in DEFAULT_CATALOG_INVENTORY:
        matched_entry = DEFAULT_CATALOG_INVENTORY[clean_sku]
    else:
        # 2. Match by product name substring
        for k, v in DEFAULT_CATALOG_INVENTORY.items():
            if clean_name and (clean_name in v["name"].lower() or v["name"].lower() in clean_name):
                matched_entry = v
                resolved_sku = k
                break

    if not matched_entry:
        # Default fallback for unlisted catalog items
        units = 10
        in_stock = True
        pname = product_name or (f"Item {clean_sku}" if clean_sku else "Product")
        LOGGER.info("[Inventory Tool] SKU '%s' not in fixed catalog; default stock=10 units available", clean_sku or "UNKNOWN")
        return InventoryResult(
            sku=clean_sku or "CAT-GEN-01",
            product_name=pname,
            in_stock=in_stock,
            available_units=units,
            category="General",
            unit_price=59.99,
        )

    pname = matched_entry["name"]
    units = int(matched_entry.get("stock", 0))
    in_stock = units > 0
    cat = matched_entry.get("category", "General")
    price = float(matched_entry.get("price", 0.0))

    # Find alternatives in same category if out of stock
    alternatives: List[Dict[str, Any]] = []
    if not in_stock:
        for k, v in DEFAULT_CATALOG_INVENTORY.items():
            if k != resolved_sku and v.get("category") == cat and v.get("stock", 0) > 0:
                alternatives.append({
                    "sku": k,
                    "name": v["name"],
                    "price": v["price"],
                    "stock": v["stock"],
                })

    LOGGER.info(
        "[Inventory Tool] Stock check for '%s' (SKU: %s): in_stock=%s, units=%d, alternatives=%d",
        pname,
        resolved_sku,
        in_stock,
        units,
        len(alternatives),
    )

    return InventoryResult(
        sku=resolved_sku,
        product_name=pname,
        in_stock=in_stock,
        available_units=units,
        category=cat,
        unit_price=price,
        alternative_products=alternatives,
    )


def execute_refund_action(
    order_number: str,
    customer_email: str,
    customer_id: Union[str, int] = "",
    amount: Optional[float] = None,
    reason: str = "Defective/Damaged product verified via multimodal inspection",
) -> Dict[str, Any]:
    """Execute refund initiation action and record state in Supabase."""
    ref_id = f"REF-{str(uuid4())[:8].upper()}"
    LOGGER.info(
        "[Action Engine] EXECUTING REFUND: Order=%s | Customer=%s | RefID=%s | Reason=%s",
        order_number,
        customer_email,
        ref_id,
        reason,
    )

    # Persist state update in customer issues
    try:
        from app.db.customer_memory import create_or_update_customer_issue
        if customer_id and str(customer_id) not in {"0", ""}:
            create_or_update_customer_issue(
                customer_id=customer_id,
                issue_title=f"Refund Request ({order_number})",
                description=f"Refund initiated for Order {order_number}. Reason: {reason}",
                status="refund_initiated",
                priority="high",
                resolution_notes=f"Full refund initiated (Ref: {ref_id}). Pending payout gateway settlement.",
                order_number=order_number,
                suggested_action="Full Refund",
            )
    except Exception as exc:
        LOGGER.warning("[Action Engine] Could not persist refund issue in Supabase: %s", exc)

    return {
        "status": "refund_initiated",
        "refund_id": ref_id,
        "order_number": order_number,
        "customer_email": customer_email,
        "amount": amount,
        "reason": reason,
        "action_taken": "Full refund authorized and queued in billing gateway.",
    }


def execute_exchange_action(
    order_number: str,
    customer_email: str,
    sku: str,
    replacement_sku: str,
    customer_id: Union[str, int] = "",
    reason: str = "Damaged item replacement exchange",
) -> Dict[str, Any]:
    """Execute replacement exchange dispatch and record state in Supabase."""
    ex_id = f"EX-{str(uuid4())[:8].upper()}"
    LOGGER.info(
        "[Action Engine] EXECUTING EXCHANGE: Order=%s | OriginalSKU=%s | ReplacementSKU=%s | ExID=%s",
        order_number,
        sku,
        replacement_sku,
        ex_id,
    )

    try:
        from app.db.customer_memory import create_or_update_customer_issue
        if customer_id and str(customer_id) not in {"0", ""}:
            create_or_update_customer_issue(
                customer_id=customer_id,
                issue_title=f"Replacement Exchange ({order_number})",
                description=f"Exchange order {ex_id} created for replacement SKU {replacement_sku}.",
                status="exchange_pending",
                priority="high",
                resolution_notes=f"Replacement order {ex_id} created with prepaid return label.",
                order_number=order_number,
                suggested_action="Instant Replacement Dispatch",
            )
    except Exception as exc:
        LOGGER.warning("[Action Engine] Could not persist exchange issue in Supabase: %s", exc)

    return {
        "status": "exchange_pending",
        "exchange_id": ex_id,
        "order_number": order_number,
        "original_sku": sku,
        "replacement_sku": replacement_sku,
        "customer_email": customer_email,
        "action_taken": f"Replacement shipment {ex_id} queued. Prepaid return shipping label generated.",
    }
