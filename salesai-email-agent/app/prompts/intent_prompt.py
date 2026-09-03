"""Prompt builder for intent classification (SalesAI V3)."""

from typing import List, Optional

INTENT_TAXONOMY = [
    "product_inquiry",
    "product_recommendation",
    "product_availability",
    "product_comparison",
    "product_details",
    "bulk_order",
    "order_tracking",
    "order_cancellation",
    "order_status",
    "reorder_request",
    "shipping_inquiry",
    "delivery_issue",
    "delayed_delivery",
    "address_change",
    "failed_delivery",
    "return_request",
    "refund_request",
    "refund_status",
    "exchange_request",
    "damaged_product",
    "defective_product",
    "payment_issue",
    "payment_methods",
    "payment_security",
    "warranty_inquiry",
    "warranty_claim",
    "general_support",
    "technical_issue",
    "complaint",
    "escalation_request",
    "greeting",
    "thanks",
    "other",
]


def build_intent_classifier_prompt(message: str, history: str = "", taxonomy: Optional[List[str]] = None) -> str:
    """Return the centralized prompt used for intent detection."""
    allowed = taxonomy or INTENT_TAXONOMY
    history_block = history.strip()
    history_text = f"\nConversation history:\n{history_block}\n" if history_block else ""
    return (
        "You are the Intent Classification module of ShopiFyX SalesAI.\n\n"
        "Your task is to identify the PRIMARY intent and goal of the customer's message.\n\n"
        "Available intents:\n"
        + "- " + "\n- ".join(allowed) + "\n\n"
        + "CRITICAL DISAMBIGUATION RULES:\n"
        + "1. PRE-PURCHASE vs. POST-PURCHASE:\n"
        + "   - If the customer mentions an item in the context of an existing order ('I ordered shoes', 'order was shipped', 'package arrived'), DO NOT classify as product_details or product_inquiry.\n"
        + "   - If the customer is facing an issue with shipment, delivery partner contact, being unavailable/away, or missed delivery, classify as 'delayed_delivery' or 'delivery_issue'.\n"
        + "   - Only use 'product_inquiry' / 'product_details' if the customer is asking questions before purchasing (e.g., 'What material is this shoe?', 'Is size 10 in stock?').\n"
        + "2. CORE OBJECTIVE:\n"
        + "   - Focus on what problem the customer wants resolved ('What can I do now?', 'Can I reschedule?', 'Where is it?').\n"
        + "3. Select exactly ONE primary intent from the allowed list.\n"
        + "4. Do not invent an intent outside the provided taxonomy.\n"
        + "5. Use the conversation history when available.\n"
        + "6. Do not answer the customer. Only classify the message.\n\n"
        + "Return ONLY valid JSON:\n\n"
        + "{\n"
        + '  "intent": "<one_intent>",\n'
        + '  "confidence": 0.0,\n'
        + '  "secondary_intents": [],\n'
        + '  "evidence": "<short explanation>"\n'
        + "}\n\n"
        + history_text
        + "Customer message:\n"
        + message
        + "\n"
    )

