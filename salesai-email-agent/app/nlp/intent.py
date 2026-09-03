"""Intent classification module for SalesAI using Gemini API.

This version follows the V3 taxonomy and emits structured JSON with a
primary intent, confidence score, optional secondary intents, and evidence.
"""

from __future__ import annotations


import json
import logging
import os
import re
from typing import Any, Dict



from dotenv import load_dotenv

from app.prompts.intent_prompt import build_intent_classifier_prompt


load_dotenv()

LOGGER = logging.getLogger(__name__)

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

ALLOWED_INTENTS = set(INTENT_TAXONOMY)
FALLBACK_RESULT = {"intent": "general_support", "confidence": 0.45, "secondary_intents": [], "evidence": "Ambiguous customer message."}


def _model_candidates_from_env() -> list[str]:
    configured = os.getenv("GEMINI_MODEL", "").strip()
    candidates = [
        configured,
        "gemini-3.6-flash",
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "models/gemini-3.6-flash",
        "models/gemini-2.5-flash",
        "models/gemini-1.5-flash",
    ]
    return [name for name in candidates if name]


def _generate_intent_gemini(api_key: str, prompt: str) -> str:
    candidates = _model_candidates_from_env()
    # 1. Try modern google.genai Client
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        for model_name in candidates:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = (getattr(response, "text", "") or "").strip()
                if text:
                    return text
            except Exception as exc:
                LOGGER.debug("google.genai candidate %s failed: %s", model_name, exc)
                continue
    except ImportError:
        pass

    # 2. Try legacy google.generativeai
    try:
        # pyrefly: ignore [missing-import]
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        for model_name in candidates:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                response_text = getattr(response, "text", "") or ""
                if response_text.strip():
                    return response_text
            except Exception as exc:
                LOGGER.debug("google.generativeai candidate %s failed: %s", model_name, exc)
                continue
    except ImportError:
        pass

    return ""



def _extract_json_object(text: str) -> str:
    if not text:
        return ""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + 1]


def _normalize_confidence(value: Any) -> float:
    try:
        parsed = float(value)
        if 0.0 <= parsed <= 1.0:
            return parsed
    except Exception:
        pass
    lower = str(value).strip().lower()
    if lower in {"high", "very_high"}:
        return 0.9
    if lower in {"medium", "moderate"}:
        return 0.7
    if lower in {"low", "weak"}:
        return 0.45
    return 0.45


from app.nlp.preprocess import strip_email_history


def _heuristic_fallback(text: str) -> Dict[str, Any]:
    raw_text = strip_email_history(text or "")
    t = (raw_text or "").lower()

    # 1. Post-Purchase Delivery, Shipping, and Missed Delivery Issues (High Precedence)
    delivery_issue_patterns = [
        "delivery partner", "tried to contact", "contact me", "not available", "wasn't available",
        "was not available", "business trip", "out of town", "out of station", "missed delivery",
        "failed delivery", "attempted delivery", "delivery attempt", "reschedule", "rescheduling",
        "what can i do now", "what should i do now", "order was shipped", "when the order was shipped",
        "delivery delayed", "package delayed", "courier called", "delivery boy", "delivery person"
    ]
    if any(pattern in t for pattern in delivery_issue_patterns):
        return {
            "intent": "delayed_delivery",
            "confidence": 0.90,
            "secondary_intents": ["delivery_issue", "order_status"],
            "evidence": "Customer describes a delivery attempt, shipping issue, or schedule conflict.",
        }

    if any(word in t for word in ["change address", "update address", "wrong address", "change my delivery address", "deliver to another"]):
        return {"intent": "address_change", "confidence": 0.90, "secondary_intents": ["delivery_issue"], "evidence": "Customer requested address change."}

    if any(word in t for word in ["where is my order", "tracking", "track order", "track my package", "shipping status", "arrived late", "delayed", "not received", "still not arrived"]):
        return {"intent": "delayed_delivery" if any(w in t for w in ["delayed", "late", "still not"]) else "order_tracking", "confidence": 0.88, "secondary_intents": ["order_status"], "evidence": "Customer reports a late delivery or requests tracking."}

    if any(word in t for word in ["international shipping", "ship to", "shipping policy", "deliver to lakshadweep", "deliver to kashmir", "shipping charges", "delivery time"]):
        return {"intent": "shipping_inquiry", "confidence": 0.90, "secondary_intents": ["general_support"], "evidence": "Customer inquired about shipping coverage or policies."}

    # 2. Refunds & Returns
    if any(word in t for word in ["refund", "money back", "return my money", "refund status"]):
        return {"intent": "refund_request", "confidence": 0.88, "secondary_intents": ["warranty_claim"], "evidence": "Customer requests a refund or money back."}
    if any(word in t for word in ["return", "exchange", "send it back", "replace item"]):
        return {"intent": "return_request", "confidence": 0.90, "secondary_intents": ["exchange_request"], "evidence": "Customer asks about returning or exchanging a product."}

    # 3. Damaged / Defective / Quality
    if any(word in t for word in ["broken", "defective", "stopped working", "not working", "damaged", "torn", "faulty"]):
        return {"intent": "damaged_product", "confidence": 0.88, "secondary_intents": ["warranty_claim"], "evidence": "Customer reports a product defect or damage."}

    # 4. Order Cancellation
    if any(word in t for word in ["cancel order", "cancel my order", "cancellation"]):
        return {"intent": "order_cancellation", "confidence": 0.92, "secondary_intents": ["refund_request"], "evidence": "Customer requested order cancellation."}

    # 5. Pre-Purchase Inquiries & Recommendations (Requires specific exploratory phrasing)
    if any(phrase in t for phrase in ["recommend", "suggest", "which one should i buy", "which one is better", "what do you suggest", "looking for shoes", "looking for a"]):
        return {"intent": "product_recommendation", "confidence": 0.90, "secondary_intents": ["product_inquiry"], "evidence": "Customer wants a product recommendation."}

    if any(phrase in t for phrase in ["how much", "price of", "cost of", "in stock", "is it available", "available in size", "material of", "fabric of", "specifications", "specs for", "details of"]):
        return {"intent": "product_details", "confidence": 0.85, "secondary_intents": ["product_inquiry"], "evidence": "Customer asks for product-specific information or specifications."}

    # 6. Customer Support / Greetings / Thanks
    if any(word in t for word in ["nobody has helped", "three times", "not fixed", "complaint", "terrible", "unacceptable"]):
        return {"intent": "complaint", "confidence": 0.90, "secondary_intents": ["escalation_request"], "evidence": "Customer raises a complaint about unresolved support."}
    if any(word in t for word in ["thank you", "thanks", "appreciate", "great support"]) and not any(w in t for w in ["but", "however", "what can", "what should", "help"]):
        return {"intent": "thanks", "confidence": 0.94, "secondary_intents": [], "evidence": "Customer is expressing appreciation."}
    if re.search(r"\b(hello|hi|hey|good morning|good evening)\b", t) and len(t.split()) <= 4:
        return {"intent": "greeting", "confidence": 0.96, "secondary_intents": [], "evidence": "Customer opens with a greeting."}

    return FALLBACK_RESULT.copy()



def _parse_model_json(response_text: str) -> Dict[str, Any]:
    cleaned = _extract_json_object(response_text)
    if not cleaned:
        return FALLBACK_RESULT.copy()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return FALLBACK_RESULT.copy()

    intent = str(data.get("intent", "")).strip().lower()
    secondary = data.get("secondary_intents") or []
    if isinstance(secondary, str):
        secondary = [secondary]
    secondary_clean = [str(item).strip().lower() for item in secondary if str(item).strip()]
    secondary_clean = [item for item in secondary_clean if item in ALLOWED_INTENTS][:2]

    if intent not in ALLOWED_INTENTS:
        return FALLBACK_RESULT.copy()

    confidence = _normalize_confidence(data.get("confidence", 0.5))
    evidence = str(data.get("evidence", "")).strip() or "Customer message indicates this intent."

    return {
        "intent": intent,
        "confidence": confidence,
        "secondary_intents": secondary_clean,
        "evidence": evidence,
    }


def classify_intent(text: str, history: str = "") -> Dict[str, Any]:
    if not text or not text.strip():
        LOGGER.info("Intent input text is empty. Falling back to default intent.")
        return FALLBACK_RESULT.copy()

    clean_text_input = strip_email_history(text)
    api_key = os.getenv("GEMINI_API_KEY", "")
    prompt = build_intent_classifier_prompt(clean_text_input, history=history, taxonomy=list(INTENT_TAXONOMY))

    if not api_key:
        result = _heuristic_fallback(clean_text_input)
        LOGGER.info("Intent input=%r | intent=%s | confidence=%.2f", clean_text_input, result["intent"], result["confidence"])
        return result

    try:
        response_text = _generate_intent_gemini(api_key, prompt)
        result = _parse_model_json(response_text)
        if result == FALLBACK_RESULT:
            result = _heuristic_fallback(clean_text_input)
        LOGGER.info("Intent input=%r | intent=%s | confidence=%.2f", clean_text_input, result["intent"], result["confidence"])
        return result
    except Exception as exc:
        LOGGER.warning("Gemini intent classification failed, using fallback: %s", exc)
        result = _heuristic_fallback(clean_text_input)
        LOGGER.info("Intent input=%r | intent=%s | confidence=%.2f", clean_text_input, result["intent"], result["confidence"])
        return result



def classify_intent_for_email(email_id: str, text: str) -> Dict[str, Any]:
    result = classify_intent(text)
    LOGGER.info("email_id=%s | intent=%s | confidence=%.2f", email_id, result["intent"], result["confidence"])
    return result


def _confidence_to_float(confidence_value: Any) -> float:
    return _normalize_confidence(confidence_value)


def detect_intent_emotion_gemini(text: str) -> Dict[str, float | str]:
    result = classify_intent(text)
    return {
        "intent": result.get("intent", "general_support"),
        "intent_confidence": _confidence_to_float(result.get("confidence", 0.45)),
    }
