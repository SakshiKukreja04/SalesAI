"""Memory-aware Intent and Emotion Classifier (SalesAI V3).

Uses customer memory as contextual evidence without allowing memory to override
the current customer message.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.config import settings
from app.memory.memory_models import CustomerMemory
from app.prompts.emotion_prompt import EMOTION_TAXONOMY
from app.prompts.intent_emotion_memory_prompt import build_memory_aware_nlp_prompt
from app.prompts.intent_prompt import INTENT_TAXONOMY

LOGGER = logging.getLogger(__name__)

ALLOWED_INTENTS = set(INTENT_TAXONOMY)
ALLOWED_EMOTIONS = set(EMOTION_TAXONOMY)


class IntentEmotionMemoryResult(BaseModel):
    """Strict structured output model for memory-aware intent and emotion classification."""

    intent: str = "general_support"
    intent_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    emotion: str = "neutral"
    emotion_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning_summary: str = "Classified from customer message."
    memory_used: bool = False


def _extract_json_object(text: str) -> str:
    """Extract JSON string block from LLM output."""
    if not text:
        return ""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + 1]


def _model_candidates() -> List[str]:
    """Return model candidate list."""
    configured = getattr(settings, "gemini_model", None) or os.getenv("GEMINI_MODEL", "")
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



def _format_memory_for_nlp(
    customer_memory: Optional[CustomerMemory],
) -> tuple[str, str, str]:
    """Extract and format memory summary, open issues, and recent interactions for the NLP prompt."""
    if not customer_memory or customer_memory.is_empty:
        return "", "", ""

    # 1. Summary
    summary_parts = []
    if customer_memory.profile:
        prof = customer_memory.profile
        summary_parts.append(f"Customer ID: {prof.customer_id}")
        summary_parts.append(f"Total Interactions: {prof.total_interactions}")
        if prof.name and prof.name != "Valued Customer":
            summary_parts.append(f"Name: {prof.name}")
    if customer_memory.risk_level != "LOW":
        summary_parts.append(f"Risk Level: {customer_memory.risk_level}")
    if customer_memory.interests:
        prod_names = [i.product_name for i in customer_memory.interests[:3]]
        summary_parts.append(f"Recent Product Interests: {', '.join(prod_names)}")
    memory_summary = "\n".join(f"- {p}" for p in summary_parts)

    # 2. Open Issues
    issue_lines = []
    if customer_memory.open_issues:
        for issue in customer_memory.open_issues[:3]:
            issue_lines.append(f"- [{issue.status.upper()}] {issue.issue_title} (Priority: {issue.priority}) - {issue.description[:100]}")
    open_issues = "\n".join(issue_lines)

    # 3. Recent Interactions
    interaction_lines = []
    if customer_memory.recent_conversations:
        for conv in customer_memory.recent_conversations[:3]:
            cust_snippet = (conv.customer_message or conv.normalized_message or "")[:90].strip()
            reply_snippet = (conv.generated_reply or "")[:90].strip()
            interaction_lines.append(
                f"- Past turn (Intent: {conv.intent}, Emotion: {conv.emotion}):\n"
                f"  Customer: \"{cust_snippet}\"\n"
                f"  Support: \"{reply_snippet}\""
            )
    recent_interactions = "\n".join(interaction_lines)

    return memory_summary, open_issues, recent_interactions


from app.nlp.preprocess import strip_email_history


def _heuristic_nlp_disambiguation(
    message: str,
    customer_memory: Optional[CustomerMemory] = None,
    kb_context: Optional[List[str]] = None,
) -> IntentEmotionMemoryResult:
    """Deterministic NLP classifier with memory-assisted ambiguity resolution."""
    raw_text = strip_email_history(message or "")
    msg_lower = (raw_text or "").strip().lower()
    memory_used = False
    reasoning = "Classified directly from message content."

    # 1. Emotion detection from CURRENT message
    emotion = "neutral"
    emotion_conf = 0.85

    # Check for strong explicit emotions first
    if any(w in msg_lower for w in ["furious", "unacceptable", "terrible", "worst", "angry", "disaster"]):
        emotion = "angry"
        emotion_conf = 0.95
    elif any(w in msg_lower for w in ["frustrated", "still waiting", "annoyed", "ridiculous", "no response", "not happy"]):
        emotion = "frustrated"
        emotion_conf = 0.85
    elif any(w in msg_lower for w in ["urgent", "asap", "emergency", "immediately", "right now"]):
        emotion = "urgent"
        emotion_conf = 0.90
    elif any(w in msg_lower for w in ["worried", "concerned", "anxious", "scared", "missed delivery", "trip to", "out of town", "business trip"]):
        emotion = "worried"
        emotion_conf = 0.85
    elif any(w in msg_lower for w in ["what can i do", "what should i do", "confused", "don't understand", "not sure", "unclear", "how do i"]):
        emotion = "confused"
        emotion_conf = 0.85
    elif any(w in msg_lower for w in ["disappointed", "let down", "expected better"]):
        emotion = "disappointed"
        emotion_conf = 0.85
    elif any(w in msg_lower for w in ["awesome", "great", "perfect!"]) and not any(w in msg_lower for w in ["what can", "what should", "help", "problem", "issue", "contact me", "partner"]):
        emotion = "happy"
        emotion_conf = 0.90
    elif any(w in msg_lower for w in ["thank", "thanks", "appreciate", "resolved", "worked"]):
        # Only mark satisfied if this isn't just a polite opening followed by a question/problem
        has_problem = any(w in msg_lower for w in ["what can", "what should", "how", "partner", "contact me", "not available", "trip", "delay", "issue", "problem", "help"])
        if not has_problem:
            emotion = "satisfied"
            emotion_conf = 0.90

    # 2. Intent detection from CURRENT message first (Post-Purchase & Delivery Priority)
    intent = "general_support"
    intent_conf = 0.60

    # Delivery & Shipping Issues
    delivery_patterns = [
        "delivery partner", "tried to contact", "contact me", "not available", "wasn't available",
        "was not available", "business trip", "out of town", "out of station", "missed delivery",
        "failed delivery", "attempted delivery", "delivery attempt", "reschedule", "rescheduling",
        "what can i do now", "what should i do now", "order was shipped", "when the order was shipped",
        "delivery delayed", "package delayed", "courier called", "delivery boy", "delivery person"
    ]
    if any(p in msg_lower for p in delivery_patterns):
        intent = "delayed_delivery"
        intent_conf = 0.90
        reasoning = "Customer reports delivery attempt, scheduling dilemma, or shipping delay."
    elif any(w in msg_lower for w in ["change address", "update address", "wrong address", "change delivery address"]):
        intent = "address_change"
        intent_conf = 0.90
        reasoning = "Customer requested shipping address change."
    elif "track" in msg_lower or "where is my order" in msg_lower or "shipping status" in msg_lower:
        intent = "order_tracking"
        intent_conf = 0.90
        reasoning = "Customer asked for order tracking status."
    elif any(w in msg_lower for w in ["international shipping", "ship to", "deliver to", "shipping policy", "shipping cost", "delivery time"]):
        intent = "shipping_inquiry"
        intent_conf = 0.90
        reasoning = "Customer inquired about shipping policies or destinations."
    elif "refund" in msg_lower or "money back" in msg_lower:
        intent = "refund_request"
        intent_conf = 0.90
        reasoning = "Customer explicitly requested a refund."
    elif "return" in msg_lower or "send back" in msg_lower:
        intent = "return_request"
        intent_conf = 0.90
        reasoning = "Customer explicitly asked for a return."
    elif "cancel" in msg_lower and "order" in msg_lower:
        intent = "order_cancellation"
        intent_conf = 0.92
        reasoning = "Customer requested order cancellation."
    elif "broken" in msg_lower or "damaged" in msg_lower or "defective" in msg_lower or "torn" in msg_lower:
        intent = "damaged_product"
        intent_conf = 0.88
        reasoning = "Customer reported a damaged or defective item."
    elif "warranty" in msg_lower:
        intent = "warranty_claim" if any(w in msg_lower for w in ["claim", "broken", "repair", "replace"]) else "warranty_inquiry"
        intent_conf = 0.88
        reasoning = "Customer inquired about warranty."
    elif any(w in msg_lower for w in ["recommend", "which shoes should", "what do you suggest", "looking for a recommendation", "which is better"]):
        intent = "product_recommendation"
        intent_conf = 0.88
        reasoning = "Customer requested product recommendations."
    elif any(w in msg_lower for w in ["how much is", "price of", "cost of", "in stock", "is it available", "available in size", "material of", "fabric of", "specifications for", "specs for", "details for"]):
        intent = "product_inquiry"
        intent_conf = 0.88
        reasoning = "Customer asked about product specifications, material, availability, or pricing."
    elif re.search(r"\b(hi|hello|hey|good morning|good afternoon|good evening)\b", msg_lower) and len(msg_lower.split()) <= 4:
        intent = "greeting"
        intent_conf = 0.95
        reasoning = "Customer sent a greeting."
    elif re.search(r"\b(thanks|thank you|that worked|all set)\b", msg_lower) and not any(w in msg_lower for w in ["what can", "what should", "help", "issue", "contact me"]):
        intent = "thanks"
        intent_conf = 0.90
        reasoning = "Customer expressed appreciation."


    # 3. Ambiguity Resolution via Customer Memory (for referential / continuation messages)
    is_referential = (
        len(msg_lower.split()) <= 6
        or any(phrase in msg_lower for phrase in ["still waiting", "same issue", "same problem", "same one", "what about it", "any update", "status on this", "did it go through", "that worked"])
    )

    if is_referential and customer_memory:
        open_issues = customer_memory.open_issues or []
        recent_convs = customer_memory.recent_conversations or []
        interests = customer_memory.interests or []

        # Example: "Still waiting for it."
        if "still waiting" in msg_lower or "any update" in msg_lower or "status on this" in msg_lower:
            if open_issues:
                top_issue = open_issues[0]
                issue_title = top_issue.issue_title.lower()
                if "refund" in issue_title:
                    intent = "refund_status"
                elif any(k in issue_title for k in ["delivery", "order", "shipping"]):
                    intent = "delayed_delivery"
                else:
                    intent = "escalation_request"
                intent_conf = 0.88
                memory_used = True
                reasoning = f"Resolved 'still waiting' reference using open issue: {top_issue.issue_title}."
            elif recent_convs:
                top_conv = recent_convs[0]
                if top_conv.intent in {"refund_request", "refund_status"}:
                    intent = "refund_status"
                elif top_conv.intent in {"order_tracking", "order_status", "delivery_issue"}:
                    intent = "delayed_delivery"
                else:
                    intent = top_conv.intent
                intent_conf = 0.85
                memory_used = True
                reasoning = f"Resolved inquiry reference using recent interaction intent: {top_conv.intent}."

        # Example: "Same issue again."
        elif "same issue" in msg_lower or "same problem" in msg_lower:
            if open_issues:
                top_issue = open_issues[0]
                issue_title = top_issue.issue_title.lower()
                if "refund" in issue_title:
                    intent = "refund_request"
                elif "damaged" in issue_title or "defective" in issue_title:
                    intent = "damaged_product"
                elif "delivery" in issue_title or "delayed" in issue_title:
                    intent = "delivery_issue"
                else:
                    intent = "complaint"
                intent_conf = 0.88
                memory_used = True
                reasoning = f"Resolved 'same issue' from open issue: {top_issue.issue_title}."
            elif recent_convs:
                intent = recent_convs[0].intent
                intent_conf = 0.85
                memory_used = True
                reasoning = f"Resolved repeat issue using recent turn intent: {recent_convs[0].intent}."

        # Example: "Can I get the same one?"
        elif "same one" in msg_lower or "get that one" in msg_lower:
            if interests:
                intent = "product_inquiry"
                intent_conf = 0.86
                memory_used = True
                reasoning = f"Resolved 'same one' from tracked product interest: {interests[0].product_name}."
            elif recent_convs and recent_convs[0].intent in {"product_inquiry", "product_recommendation"}:
                intent = "product_inquiry"
                intent_conf = 0.85
                memory_used = True
                reasoning = "Resolved product query from recent conversation history."

        # Example: "Thanks, that worked."
        elif "that worked" in msg_lower or "resolved" in msg_lower:
            intent = "thanks"
            emotion = "satisfied"
            intent_conf = 0.92
            emotion_conf = 0.90
            memory_used = True
            reasoning = "Customer acknowledged successful resolution of previous issue."

    return IntentEmotionMemoryResult(
        intent=intent if intent in ALLOWED_INTENTS else "general_support",
        intent_confidence=intent_conf,
        emotion=emotion if emotion in ALLOWED_EMOTIONS else "neutral",
        emotion_confidence=emotion_conf,
        reasoning_summary=reasoning,
        memory_used=memory_used,
    )


def classify_intent_and_emotion_with_memory(
    message: str,
    customer_memory: Optional[CustomerMemory] = None,
    kb_context: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Classify customer intent and emotion using memory as supporting contextual evidence."""
    clean_msg = strip_email_history((message or "").strip())
    if not clean_msg:
        clean_msg = (message or "").strip()
    if not clean_msg:
        return {
            "intent": "general_support",
            "intent_confidence": 0.50,
            "emotion": "neutral",
            "emotion_confidence": 0.50,
            "reasoning_summary": "Empty customer message.",
            "memory_used": False,
        }

    api_key = getattr(settings, "gemini_api_key", None) or os.getenv("GEMINI_API_KEY", "")
    
    # Extract memory sections
    mem_summary, open_issues, recent_interactions = _format_memory_for_nlp(customer_memory)
    kb_text = "\n\n".join(kb_context[:2]) if kb_context else ""

    if not api_key:
        heuristic = _heuristic_nlp_disambiguation(clean_msg, customer_memory, kb_context)
        return heuristic.model_dump()

    prompt = build_memory_aware_nlp_prompt(
        current_message=clean_msg,
        customer_memory_summary=mem_summary,
        recent_interactions=recent_interactions,
        open_issues=open_issues,
        kb_context=kb_text,
    )

    try:
        # 1. Try modern google.genai Client
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            for model_name in _model_candidates():
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    text = (getattr(response, "text", "") or "").strip()
                    if text:
                        json_str = _extract_json_object(text)
                        if json_str:
                            data = json.loads(json_str)
                            validated = IntentEmotionMemoryResult.model_validate(data)
                            if validated.intent not in ALLOWED_INTENTS:
                                validated.intent = "general_support"
                            if validated.emotion not in ALLOWED_EMOTIONS:
                                validated.emotion = "neutral"
                            return validated.model_dump()
                except Exception as exc:
                    LOGGER.debug("google.genai candidate %s failed in memory classifier: %s", model_name, exc)
                    continue
        except ImportError:
            pass

        # 2. Try legacy google.generativeai
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            for model_name in _model_candidates():
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    text = (getattr(response, "text", "") or "").strip()
                    if text:
                        json_str = _extract_json_object(text)
                        if json_str:
                            data = json.loads(json_str)
                            validated = IntentEmotionMemoryResult.model_validate(data)
                            if validated.intent not in ALLOWED_INTENTS:
                                validated.intent = "general_support"
                            if validated.emotion not in ALLOWED_EMOTIONS:
                                validated.emotion = "neutral"
                            return validated.model_dump()
                except Exception as exc:
                    LOGGER.debug("google.generativeai candidate %s failed in memory classifier: %s", model_name, exc)
                    continue
        except ImportError:
            pass

        heuristic = _heuristic_nlp_disambiguation(clean_msg, customer_memory, kb_context)
        return heuristic.model_dump()

    except Exception as exc:
        LOGGER.warning("Memory-aware NLP classification failed, falling back to heuristic: %s", exc)
        heuristic = _heuristic_nlp_disambiguation(clean_msg, customer_memory, kb_context)
        return heuristic.model_dump()

