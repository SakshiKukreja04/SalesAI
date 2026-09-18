"""Read-only, intent-aware retrieval from the existing Neo4j graph."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.neo4j_client import neo4j_client

LOGGER = logging.getLogger(__name__)


def _records(query: str, **params: Any) -> List[Dict[str, Any]]:
    if not neo4j_client.configured:
        return []
    return neo4j_client.read_records(query, **params)


def get_customer_context(email: str) -> Dict[str, Any]:
    """Retrieve a customer and bounded order/product/shipment context."""
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return {"customer_found": False, "customer": None, "orders": []}

    query = """
    MATCH (c:Customer)
    WHERE toLower(coalesce(c.contact_email, c.email, '')) = $email
    OPTIONAL MATCH (c)-[:PLACED]->(o:Order)
    OPTIONAL MATCH (o)-[contains:CONTAINS]->(p:Product)
    OPTIONAL MATCH (o)-[:HAS_SHIPMENT]->(s:Shipment)
    RETURN c.id AS customer_id,
           c.name AS customer_name,
           coalesce(c.contact_email, c.email) AS customer_email,
           c.customer_tier AS customer_tier,
           c.customer_status AS customer_status,
           o.id AS order_id,
           o.order_number AS order_number,
           o.status AS order_status,
           o.order_date AS order_date,
           o.total_amount AS total_amount,
           p.name AS product_name,
           p.sku AS sku,
           contains.quantity AS quantity,
           contains.unit_price AS unit_price,
           s.status AS shipment_status,
           s.carrier AS carrier,
           s.shipped_at AS shipped_at,
           s.tracking_number AS tracking_number,
           s.estimated_delivery_at AS estimated_delivery,
           s.delivered_at AS delivered_at
    ORDER BY o.order_date DESC
    LIMIT 50
    """
    rows = _records(query, email=normalized_email)
    if not rows:
        return {"customer_found": False, "customer": None, "orders": []}

    first = rows[0]
    customer = {
        "id": first.get("customer_id"),
        "name": first.get("customer_name"),
        "email": first.get("customer_email"),
        "tier": first.get("customer_tier"),
        "status": first.get("customer_status"),
    }
    orders: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        order_key = row.get("order_id") or row.get("order_number")
        if not order_key:
            continue
        order = orders.setdefault(
            str(order_key),
            {
                "id": row.get("order_id"),
                "order_number": row.get("order_number"),
                "status": row.get("order_status"),
                "order_date": row.get("order_date"),
                "total_amount": row.get("total_amount"),
                "products": [],
                "shipment": {
                    "status": row.get("shipment_status"),
                    "carrier": row.get("carrier"),
                    "shipped_at": row.get("shipped_at"),
                    "tracking_number": row.get("tracking_number"),
                    "estimated_delivery": row.get("estimated_delivery"),
                    "delivered_at": row.get("delivered_at"),
                },
            },
        )
        if row.get("product_name"):
            order["products"].append(
                {
                    "name": row.get("product_name"),
                    "sku": row.get("sku"),
                    "quantity": row.get("quantity"),
                    "unit_price": row.get("unit_price"),
                }
            )

    return {"customer_found": True, "customer": customer, "orders": list(orders.values())}


def get_customer_conversations(email: str, limit: int = 10) -> List[Dict[str, Any]]:
    query = """
    MATCH (c:Customer)-[:HAD_CONVERSATION]->(conversation:Conversation)
    WHERE toLower(coalesce(c.contact_email, c.email, '')) = $email
    RETURN conversation.id AS id,
           conversation.subject AS subject,
           conversation.customer_message AS customer_message,
           conversation.intent AS intent,
           conversation.emotion AS emotion,
           conversation.strategy AS strategy,
           conversation.generated_reply AS generated_reply,
           conversation.confidence AS confidence,
           conversation.status AS status,
           conversation.created_at AS created_at
    ORDER BY conversation.created_at DESC
    LIMIT $limit
    """
    return _records(query, email=(email or "").strip().lower(), limit=max(1, min(limit, 50)))


def get_customer_issues(email: str, limit: int = 10) -> List[Dict[str, Any]]:
    query = """
    MATCH (c:Customer)-[:HAS_ISSUE]->(issue:Issue)
    WHERE toLower(coalesce(c.contact_email, c.email, '')) = $email
    RETURN issue.id AS id,
           issue.issue_title AS title,
           issue.issue_description AS description,
           issue.status AS status,
           issue.priority AS priority,
           issue.created_at AS created_at
    ORDER BY issue.created_at DESC
    LIMIT $limit
    """
    return _records(query, email=(email or "").strip().lower(), limit=max(1, min(limit, 50)))


def get_customer_interests(email: str, limit: int = 10) -> List[Dict[str, Any]]:
    query = """
    MATCH (c:Customer)-[:HAS_INTEREST]->(p:Product)
    WHERE toLower(coalesce(c.contact_email, c.email, '')) = $email
    OPTIONAL MATCH (p)-[:BELONGS_TO]->(category:Category)
    RETURN p.name AS name,
           p.sku AS sku,
           p.brand AS brand,
           category.name AS category,
           p.price AS price,
           p.availability AS availability,
           p.rating AS rating
    LIMIT $limit
    """
    return _records(query, email=(email or "").strip().lower(), limit=max(1, min(limit, 50)))


def get_salesai_context(email: str, intent: str = "") -> Dict[str, Any]:
    """Retrieve bounded graph context while degrading safely when Neo4j is unavailable."""
    if not neo4j_client.configured:
        return {"customer_found": False, "customer": None, "orders": [], "previous_conversations": [], "issues": [], "interests": []}

    try:
        customer_context = get_customer_context(email)
        if not customer_context["customer_found"]:
            return {**customer_context, "previous_conversations": [], "issues": [], "interests": []}

        clean_intent = (intent or "").lower()
        conversations = get_customer_conversations(email)
        issues = get_customer_issues(email) if any(word in clean_intent for word in ("complaint", "issue", "refund", "damaged", "defective", "warranty")) else []
        interests = get_customer_interests(email) if any(word in clean_intent for word in ("product", "recommend", "availability", "comparison")) else []
        return {
            **customer_context,
            "previous_conversations": conversations,
            "issues": issues,
            "interests": interests,
        }
    except Exception as exc:
        LOGGER.exception("Neo4j retrieval failed; continuing without graph context: %s", exc)
        return {"customer_found": False, "customer": None, "orders": [], "previous_conversations": [], "issues": [], "interests": []}


def format_graph_context(context: Dict[str, Any]) -> str:
    """Convert graph results into concise, non-sensitive prompt context."""
    if not context.get("customer_found"):
        return ""

    customer = context.get("customer") or {}
    lines = [
        "GRAPH BUSINESS CONTEXT:",
        f"Customer name: {customer.get('name') or 'Unavailable'}",
        f"Customer tier: {customer.get('tier') or 'Unavailable'}",
        f"Customer status: {customer.get('status') or 'Unavailable'}",
    ]
    orders = context.get("orders") or []
    if orders:
        lines.append("Orders:")
        for order in orders[:10]:
            lines.append(
                " | ".join(
                    str(value) for value in (
                        f"Order {order.get('order_number') or 'Unavailable'}",
                        f"status={order.get('status') or 'Unavailable'}",
                        f"order date={order.get('order_date') or 'Unavailable'}",
                        f"total={order.get('total_amount') or 'Unavailable'}",
                    )
                )
            )
            for product in (order.get("products") or [])[:10]:
                lines.append(
                    f"Product: {product.get('name') or 'Unavailable'}, SKU: {product.get('sku') or 'Unavailable'}, "
                    f"quantity: {product.get('quantity') or 'Unavailable'}, unit price: {product.get('unit_price') or 'Unavailable'}"
                )
            shipment = order.get("shipment") or {}
            if any(shipment.values()):
                lines.append(
                    f"Shipment: status={shipment.get('status') or 'Unavailable'}, carrier={shipment.get('carrier') or 'Unavailable'}, "
                    f"shipped at={shipment.get('shipped_at') or 'Unavailable'}, "
                    f"tracking={shipment.get('tracking_number') or 'Unavailable'}, "
                    f"estimated delivery={shipment.get('estimated_delivery') or 'Unavailable'}, "
                    f"delivered at={shipment.get('delivered_at') or 'Unavailable'}"
                )

    for label, key in (("Recent conversations", "previous_conversations"), ("Issues", "issues"), ("Interests", "interests")):
        entries = context.get(key) or []
        if entries:
            lines.append(f"{label}:")
            for entry in entries[:10]:
                values = [value for value in entry.values() if value not in (None, "")]
                lines.append("; ".join(str(value) for value in values[:6]))

    return "\n".join(lines)