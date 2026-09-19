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


_PRODUCT_STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "can", "could", "will", "would", "shall", "should",
    "i", "you", "he", "she", "it", "we", "they", "me", "my", "your", "our",
    "what", "where", "when", "which", "who", "whom", "why", "how",
    "tell", "give", "show", "please", "thanks", "thank", "hello", "hi", "hey",
    "price", "rating", "features", "specs", "available", "availability", "stock",
    "and", "or", "any", "some", "about", "looking", "much", "cost", "inquiry",
}


def search_products_graph(query_text: str = "", category: str = "", limit: int = 5) -> List[Dict[str, Any]]:
    """Search active products in the graph by name, SKU, brand, or category with relevance scoring."""
    if not neo4j_client.configured or not (query_text or category):
        return []

    clean_query = (query_text or "").strip().lower()
    clean_category = (category or "").strip().lower()

    cypher_query = """
    MATCH (p:Product)
    OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:Category)
    RETURN p.name AS name,
           p.sku AS sku,
           p.brand AS brand,
           coalesce(c.name, '') AS category,
           p.price AS price,
           p.availability AS availability,
           p.rating AS rating,
           p.description AS description
    """
    records = _records(cypher_query)
    if not records:
        return []

    import re
    words = re.findall(r"\b[a-zA-Z0-9-]+\b", clean_query)
    keywords = [w for w in words if w not in _PRODUCT_STOPWORDS and len(w) >= 2]

    scored: List[tuple[int, Dict[str, Any]]] = []
    for prod in records:
        score = 0
        p_name = (prod.get("name") or "").lower()
        p_sku = (prod.get("sku") or "").lower()
        p_brand = (prod.get("brand") or "").lower()
        p_cat = (prod.get("category") or "").lower()
        p_desc = (prod.get("description") or "").lower()

        if clean_category and clean_category in p_cat:
            score += 50

        if p_sku and p_sku in clean_query:
            score += 100
        if p_name and p_name in clean_query:
            score += 80

        for kw in keywords:
            if kw in p_name:
                score += 30
            if kw in p_brand:
                score += 20
            if kw in p_cat:
                score += 15
            if kw in p_desc:
                score += 5

        if score > 0:
            scored.append((score, prod))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:max(1, min(limit, 20))]]


def get_salesai_context(email: str, intent: str = "", query_text: str = "") -> Dict[str, Any]:
    """Retrieve bounded graph context while degrading safely when Neo4j is unavailable."""
    if not neo4j_client.configured:
        return {
            "customer_found": False,
            "customer": None,
            "orders": [],
            "previous_conversations": [],
            "issues": [],
            "interests": [],
            "matching_products": [],
        }

    try:
        customer_context = get_customer_context(email)
        clean_intent = (intent or "").lower()

        # Product search only if intent relates to products/recommendation/inquiry
        matching_products: List[Dict[str, Any]] = []
        is_product_intent = any(word in clean_intent for word in ("product", "recommend", "availability", "comparison", "inquiry", "price", "catalog"))
        if is_product_intent and query_text:
            search_query = query_text.strip()[:200]
            if search_query:
                matching_products = search_products_graph(query_text=search_query, limit=5)

        if not customer_context["customer_found"]:
            return {
                **customer_context,
                "previous_conversations": [],
                "issues": [],
                "interests": [],
                "matching_products": matching_products,
            }

        conversations = get_customer_conversations(email)
        issues = get_customer_issues(email) if any(word in clean_intent for word in ("complaint", "issue", "refund", "damaged", "defective", "warranty")) else []
        interests = get_customer_interests(email) if is_product_intent else []
        return {
            **customer_context,
            "previous_conversations": conversations,
            "issues": issues,
            "interests": interests,
            "matching_products": matching_products,
        }
    except Exception as exc:
        LOGGER.exception("Neo4j retrieval failed; continuing without graph context: %s", exc)
        return {
            "customer_found": False,
            "customer": None,
            "orders": [],
            "previous_conversations": [],
            "issues": [],
            "interests": [],
            "matching_products": [],
        }


def format_graph_context(context: Dict[str, Any]) -> str:
    """Convert graph results into concise, non-sensitive prompt context."""
    has_customer = bool(context.get("customer_found"))
    matching_products = context.get("matching_products") or []

    if not has_customer and not matching_products:
        return ""

    lines = ["GRAPH BUSINESS CONTEXT:"]

    if has_customer:
        customer = context.get("customer") or {}
        lines.extend([
            f"Customer name: {customer.get('name') or 'Unavailable'}",
            f"Customer tier: {customer.get('tier') or 'Unavailable'}",
            f"Customer status: {customer.get('status') or 'Unavailable'}",
        ])
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

        issues = context.get("issues") or []
        if issues:
            lines.append("Issues:")
            for issue in issues[:5]:
                prio = f"[{issue.get('priority', '').upper()}] " if issue.get("priority") else ""
                lines.append(f"- {prio}{issue.get('title', '')} (Status: {issue.get('status', '')})")

        interests = context.get("interests") or []
        if interests:
            lines.append("Interests:")
            for item in interests[:5]:
                lines.append(f"- {item.get('name', '')} (SKU: {item.get('sku', '')}, Price: ₹{item.get('price', '')}, Rating: {item.get('rating', '')})")

    if matching_products:
        lines.append("Matching Catalog Products (from Knowledge Graph):")
        for prod in matching_products[:5]:
            lines.append(f"- {prod.get('name')} (SKU: {prod.get('sku')}, Category: {prod.get('category')}, Price: ₹{prod.get('price')}, Stock: {prod.get('availability')})")

    return "\n".join(lines)