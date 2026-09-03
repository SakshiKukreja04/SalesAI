"""Customer Memory Update module (SalesAI V3).

Performs structured memory extraction from completed conversation turns,
and persists updates to customer profiles, issues, interests, conversations, and ChromaDB.
Adheres strictly to deterministic deduplication and idempotency.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from app.config import settings
from app.db.customer_memory import (
    create_or_update_customer_interest,
    create_or_update_customer_issue,
    get_customer_issues,
    save_conversation_record,
    update_customer_name,
)
from app.memory.memory_models import MemoryExtractionResult, MemoryUpdate

LOGGER = logging.getLogger(__name__)

PROBLEM_INTENTS = {
    "refund_request",
    "refund_status",
    "return_request",
    "damaged_product",
    "defective_product",
    "delayed_delivery",
    "delivery_issue",
    "failed_delivery",
    "payment_issue",
    "warranty_claim",
    "complaint",
    "escalation_request",
    "technical_issue",
}

PRODUCT_INTENTS = {
    "product_inquiry",
    "product_recommendation",
    "product_availability",
    "product_comparison",
    "product_details",
    "bulk_order",
}


def _extract_json_object(text: str) -> str:
    """Extract JSON block from text."""
    if not text:
        return ""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + 1]


def _heuristic_extraction(
    customer_message: str,
    reply: str,
    intent: str,
    emotion: str,
    status: str,
) -> MemoryUpdate:
    """Deterministic fallback extraction when Gemini is unavailable."""
    msg_lower = (customer_message or "").lower()
    clean_intent = (intent or "").strip().lower()

    # Product matching heuristics
    common_products = [
        "winter jacket",
        "jacket",
        "running shoes",
        "shoes",
        "leather jacket",
        "parka",
        "t-shirt",
        "shirt",
        "jeans",
        "hoodie",
        "sneakers",
        "backpack",
        "watch",
        "laptop stand",
    ]
    mentioned = [p for p in common_products if p in msg_lower]
    interests = mentioned if clean_intent in PRODUCT_INTENTS else []

    # Name extraction heuristic (e.g., "Best, Sarah Connor", "Thanks, John")
    extracted_name = None
    name_patterns = [
        r"(?:regards|best|thanks|sincerely|from|cheers),?\s+([a-zA-Z]{2,}(?:\s+[a-zA-Z]{2,})?)",
        r"(?:my name is|i am)\s+([a-zA-Z]{2,}(?:\s+[a-zA-Z]{2,})?)",
    ]
    for pattern in name_patterns:
        match = re.search(pattern, customer_message, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            if candidate.lower() not in {"support", "shopifyx", "team", "customer", "help", "you", "salesai"}:
                extracted_name = candidate.title()
                break

    # Issue detection
    is_problem = clean_intent in PROBLEM_INTENTS or any(
        kw in msg_lower for kw in ["broken", "defective", "refund", "not delivered", "damaged", "wrong item", "complaint", "waiting"]
    )
    
    issue_title = None
    issue_status = None
    issue_priority = None
    issue_resolved = False

    # Check if this interaction indicates a resolved issue
    resolved_cues = ["thanks, that worked", "that worked", "issue resolved", "all set", "problem solved", "thank you for fixing"]
    if any(cue in msg_lower for cue in resolved_cues) or (
        status == "replied" and any(kw in (reply or "").lower() for kw in ["refund processed", "replacement has been dispatched", "issue resolved", "delivered"])
    ):
        issue_resolved = True
        issue_status = "resolved"

    if is_problem:
        issue_title = clean_intent.replace("_", " ").title()
        if not issue_status:
            issue_status = "escalated" if status == "escalated" else "open"
        
        if emotion in {"angry", "urgent"}:
            issue_priority = "urgent"
        elif emotion == "frustrated":
            issue_priority = "high"
        else:
            issue_priority = "medium"

    return MemoryUpdate(
        customer_name=extracted_name,
        products=mentioned,
        interests=interests,
        issue=issue_title,
        issue_status=issue_status,
        issue_priority=issue_priority,
        issue_resolved=issue_resolved,
        interaction_facts=[f"Intent: {intent}", f"Emotion: {emotion}"] if is_problem or interests else [],
        products_mentioned=mentioned,
        products_interested=interests,
        issue_detected=is_problem,
        issue_title=issue_title,
        issue_description=customer_message[:150].strip() if is_problem else None,
    )


def _model_candidates() -> List[str]:
    """Model candidates matching SalesAI V3 configurations."""
    configured = getattr(settings, "gemini_model", None) or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    return [configured, "gemini-2.0-flash", "gemini-1.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-flash"]


def extract_memory_from_turn(
    customer_message: str,
    reply: str,
    intent: str,
    emotion: str,
    status: str,
) -> MemoryUpdate:
    """Extract durable structured customer entities and issue states using Gemini with strict Pydantic validation."""
    api_key = getattr(settings, "gemini_api_key", None) or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return _heuristic_extraction(customer_message, reply, intent, emotion, status)

    prompt = (
        "You are the Customer Memory Extraction module of ShopiFyX SalesAI.\n"
        "Extract ONLY durable customer information from this completed interaction.\n\n"
        "INPUT:\n"
        f"Customer message:\n{customer_message}\n\n"
        f"Detected intent: {intent}\n"
        f"Detected emotion: {emotion}\n"
        f"Support reply:\n{reply}\n"
        f"Outcome status: {status}\n\n"
        "STRICT EXTRACTION RULES:\n"
        "1. Extract ONLY factual, durable customer information.\n"
        "2. 'customer_name': Extract ONLY if explicitly and reliably provided in the message or signoff, else null.\n"
        "3. 'products': List of specific product names mentioned.\n"
        "4. 'interests': Products the customer is actively interested in purchasing, exploring, or sizing for.\n"
        "5. 'issue': Summary/title of customer problem/ticket if detected (e.g. 'Refund request for damaged jacket'), else null.\n"
        "6. 'issue_status': 'open' | 'resolved' | 'escalated' (or null if no issue).\n"
        "7. 'issue_priority': 'low' | 'medium' | 'high' | 'urgent' (or null if no issue).\n"
        "8. 'issue_resolved': true if the interaction confirmed resolution of an existing or current problem, else false.\n"
        "9. 'interaction_facts': List of key durable factual statements (e.g. ['Prefers size L', 'Order #1029 was damaged']).\n\n"
        "PROHIBITED CONTENT:\n"
        "- Do NOT store temporary LLM reasoning or chain-of-thought.\n"
        "- Do NOT store arbitrary assumptions or unsupported customer preferences.\n"
        "- Do NOT store passwords, full credit card numbers, or unnecessary sensitive information.\n\n"
        "Return ONLY valid JSON matching this exact schema:\n"
        "{\n"
        '  "customer_name": null,\n'
        '  "products": [],\n'
        '  "interests": [],\n'
        '  "issue": null,\n'
        '  "issue_status": null,\n'
        '  "issue_priority": null,\n'
        '  "issue_resolved": false,\n'
        '  "interaction_facts": []\n'
        "}"
    )

    try:
        try:
            # pyrefly: ignore [missing-import]
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
                            # Sync fields
                            if "products" in data and not data.get("products_mentioned"):
                                data["products_mentioned"] = data["products"]
                            if "interests" in data and not data.get("products_interested"):
                                data["products_interested"] = data["interests"]
                            if data.get("issue"):
                                data["issue_detected"] = True
                                data["issue_title"] = data["issue"]
                            return MemoryUpdate.model_validate(data)
                except Exception:
                    continue
        except ImportError:
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
                                if "products" in data and not data.get("products_mentioned"):
                                    data["products_mentioned"] = data["products"]
                                if "interests" in data and not data.get("products_interested"):
                                    data["products_interested"] = data["interests"]
                                if data.get("issue"):
                                    data["issue_detected"] = True
                                    data["issue_title"] = data["issue"]
                                return MemoryUpdate.model_validate(data)
                    except Exception:
                        continue
            except ImportError:
                LOGGER.debug("No Google GenAI package installed, using heuristic extraction")

        return _heuristic_extraction(customer_message, reply, intent, emotion, status)

    except Exception as exc:
        LOGGER.warning("Gemini memory extraction failed, using heuristic: %s", exc)
        return _heuristic_extraction(customer_message, reply, intent, emotion, status)


def update_customer_memory(
    customer_id: Union[str, int],
    customer_email: str,
    email_id: str,
    subject: str,
    customer_message: str,
    normalized_message: str,
    intent: str,
    intent_confidence: float,
    emotion: str,
    emotion_confidence: float,
    strategy: str,
    reply: str,
    confidence: float,
    status: str,
    escalation_reason: str = "",
    selected_model: str = "gemini",
    retrieved_context_count: int = 0,
    similar_memory_count: int = 0,
) -> bool:
    """Update all persistent customer memory facets after email processing.
    
    1. Structured extraction using strict MemoryUpdate schema
    2. Update Customer Profile name if reliably provided
    3. Update Customer Interests (deduplicated by customer_id + normalized product_name)
    4. Update Customer Issues (checks open issues first, updates existing before creating new)
    5. Log Turn to Conversations table (idempotent on email_id)
    6. Save Customer Message to ChromaDB user messages (idempotent on email_id)
    7. Save Reply to ChromaDB reply memory (idempotent on email_id)
    
    Failure does NOT raise exception or block email dispatch.
    """
    if not customer_id and not customer_email:
        LOGGER.warning("update_customer_memory: Missing customer_id and customer_email")
        return False

    try:
        # Step 1: Run structured extraction
        extracted: MemoryUpdate = extract_memory_from_turn(
            customer_message=customer_message,
            reply=reply,
            intent=intent,
            emotion=emotion,
            status=status,
        )

        LOGGER.info(
            "Memory extracted for customer_id=%s: issue=%s, products=%s, resolved=%s",
            customer_id,
            extracted.issue or extracted.issue_title,
            extracted.interests or extracted.products,
            extracted.issue_resolved,
        )

        # Step 2: Update customer name if reliably provided
        if extracted.customer_name and extracted.customer_name.strip():
            update_customer_name(customer_id=customer_id, name=extracted.customer_name.strip())

        # Step 3: Update Product Interests (Deduplicated on customer_id + normalized product name)
        products_to_record = extracted.interests or extracted.products_interested or (
            extracted.products or extracted.products_mentioned if intent in PRODUCT_INTENTS else []
        )
        for prod in products_to_record:
            if prod and len(prod.strip()) > 1:
                create_or_update_customer_interest(
                    customer_id=customer_id,
                    product_name=prod.strip(),
                    status="active",
                )

        # Step 4: Update Customer Issues (Check open issues first, update existing before creating new)
        clean_intent = (intent or "").strip().lower()
        has_issue = extracted.issue or extracted.issue_detected or clean_intent in PROBLEM_INTENTS

        # Fetch existing open issues for customer
        existing_open_issues = get_customer_issues(customer_id=customer_id, status="open")

        if extracted.issue_resolved:
            # If an existing issue was resolved, update its status rather than creating a new record
            if existing_open_issues:
                for open_issue in existing_open_issues:
                    # Match by intent or keyword in title
                    if clean_intent in open_issue.issue_title.lower() or open_issue.issue_title.lower() in clean_intent or len(existing_open_issues) == 1:
                        create_or_update_customer_issue(
                            customer_id=customer_id,
                            issue_title=open_issue.issue_title,
                            description=open_issue.description,
                            status="resolved",
                            priority=open_issue.priority,
                            resolution_notes=f"Resolved via interaction: {reply[:120]}",
                        )
                        break

        elif has_issue:
            issue_title = extracted.issue or extracted.issue_title or clean_intent.replace("_", " ").title()
            issue_desc = extracted.issue_description or customer_message[:200]
            issue_priority = extracted.issue_priority or ("urgent" if emotion in {"angry", "urgent"} else "medium")
            issue_status = extracted.issue_status or ("escalated" if status == "escalated" else "open")
            resolution_notes = f"Resolution: {reply[:150]}" if issue_status == "resolved" else ""

            # Check if this issue matches an existing open issue (by title, substring, intent, or keyword overlap)
            matching_issue = None
            issue_words = set(re.findall(r"\w+", issue_title.lower()))
            for open_issue in existing_open_issues:
                open_words = set(re.findall(r"\w+", open_issue.issue_title.lower()))
                common_keywords = (issue_words & open_words) - {"issue", "request", "the", "for", "a", "an", "on", "in", "to", "problem", "ticket"}
                if (
                    issue_title.lower() in open_issue.issue_title.lower()
                    or open_issue.issue_title.lower() in issue_title.lower()
                    or bool(common_keywords)
                    or clean_intent in open_issue.issue_title.lower()
                ):
                    matching_issue = open_issue
                    break

            if matching_issue:
                # Update existing issue record
                create_or_update_customer_issue(
                    customer_id=customer_id,
                    issue_title=matching_issue.issue_title,
                    description=issue_desc,
                    status=issue_status,
                    priority=issue_priority,
                    resolution_notes=resolution_notes,
                )
            else:
                # Create new issue only when no matching open issue exists
                create_or_update_customer_issue(
                    customer_id=customer_id,
                    issue_title=issue_title,
                    description=issue_desc,
                    status=issue_status,
                    priority=issue_priority,
                    resolution_notes=resolution_notes,
                )

        # Step 5: Log conversation record (idempotent on email_id)
        conversation_saved = save_conversation_record({
            "customer_id": customer_id,
            "email_id": email_id,
            "subject": subject,
            "customer_message": customer_message,
            "normalized_message": normalized_message,
            "intent": intent,
            "intent_confidence": intent_confidence,
            "emotion": emotion,
            "emotion_confidence": emotion_confidence,
            "strategy": strategy,
            "generated_reply": reply,
            "confidence": confidence,
            "status": status,
            "escalation_reason": escalation_reason,
            "selected_model": selected_model,
            "retrieved_context_count": retrieved_context_count,
            "similar_memory_count": similar_memory_count,
        })

        # Step 6: Save Customer Message to ChromaDB user messages collection (idempotent)
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        doc_id = f"msg-{email_id or str(uuid4())[:8]}"
        if customer_message and customer_email:
            try:
                from app.rag.chroma_store import add_user_documents
                add_user_documents(
                    documents=[normalized_message or customer_message],
                    ids=[doc_id],
                    metadatas=[{
                        "source": "user_message",
                        "customer_email": customer_email.lower().strip(),
                        "customer_id": str(customer_id),
                        "subject": subject,
                        "intent": intent,
                        "emotion": emotion,
                        "timestamp": timestamp_iso,
                    }],
                )
            except Exception as exc:
                LOGGER.warning("ChromaDB user document save failed: %s", exc)

        # Step 7: Save Reply to ChromaDB reply memory collection (if successfully sent, idempotent)
        if reply and status == "replied":
            reply_doc_id = f"reply-{email_id or str(uuid4())[:8]}"
            try:
                from app.rag.chroma_store import add_reply_documents
                add_reply_documents(
                    documents=[reply],
                    ids=[reply_doc_id],
                    metadatas=[{
                        "customer_email": customer_email.lower().strip(),
                        "customer_id": str(customer_id),
                        "intent": intent,
                        "emotion": emotion,
                        "timestamp": timestamp_iso,
                        "reply_type": "generated",
                    }],
                )
            except Exception as exc:
                LOGGER.warning("ChromaDB reply document save failed: %s", exc)

        LOGGER.info(
            "Customer memory successfully updated | customer_id=%s | email=%s | conv_saved=%s",
            customer_id,
            customer_email,
            conversation_saved,
        )
        return True

    except Exception as exc:
        LOGGER.error("Failed to update customer memory for id=%s email=%s: %s", customer_id, customer_email, exc)
        return False
