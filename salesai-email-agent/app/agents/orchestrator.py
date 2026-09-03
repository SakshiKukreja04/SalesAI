"""Main multi-agent orchestration flow for customer support emails (SalesAI V3).

Integrates the persistent Customer Memory Agent into the email intelligence pipeline
with strict dependency injection, stage-by-stage structured logging, and verified flow ordering.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from app.agents.decision import build_final_email, decide_email_action, validate_email_response
from app.agents.escalation import escalate_to_human
from app.agents.generator import generate_reply, normalize_customer_response, sanitize_customer_reply
from app.agents.strategy import select_strategy
from app.config import settings
from app.db.customer_memory import normalize_email
from app.db.supabase_client import log_interaction, save_email_record
from app.email.safety_middleware import enforce_email_safety
from app.email.send_email import extract_customer_name, send_email, send_email_reply
from app.memory.customer_memory import CustomerMemoryAgent, memory_agent as default_memory_agent
from app.memory.memory_models import CustomerMemory, CustomerProfile, FormattedMemoryContext
from app.nlp.dual_llm import select_best_nlp_output
from app.nlp.emotion import detect_emotion
from app.nlp.intent import classify_intent
from app.nlp.preprocess import clean_query_text, preprocess_text
from app.rag.prompt_builder import build_strict_context_prompt
from app.rag.response_validator import SAFE_FALLBACK_RESPONSE, validate_response
from app.rag.retrieval import retrieve_relevant_chunks, retrieve_similar_user_messages

LOGGER = logging.getLogger(__name__)


def _generate_validated_reply(
    current_message: str,
    intent: str,
    emotion: str,
    strategy: str,
    kb_context: List[str],
    customer_memory: Optional[CustomerMemory] = None,
    reply_memory: Optional[List[str]] = None,
    customer_name: str = "",
) -> tuple[str, str]:
    """Generate and double-validate a fact-grounded response with customer memory."""
    strict_prompt = build_strict_context_prompt(user_query=current_message, retrieved_chunks=kb_context)

    reply = generate_reply(
        current_message=current_message,
        intent=intent,
        emotion=emotion,
        strategy=strategy,
        kb_context=kb_context,
        customer_memory=customer_memory,
        reply_memory=reply_memory,
        strict_prompt=strict_prompt,
    )
    cleaned = normalize_customer_response(reply, customer_name=customer_name)
    validation = validate_response(answer=cleaned, context_chunks=kb_context)
    if validation.is_valid:
        return cleaned, "validated"

    # Retry generation with explicit factual grounding reinforcement
    retry_prompt = (
        strict_prompt
        + "\n\nIMPORTANT: The previous answer failed factual or formatting validation. Output pure plain text, strictly following internal policy facts with no markdown formatting."
    )
    retry_reply = generate_reply(
        current_message=current_message,
        intent=intent,
        emotion=emotion,
        strategy=strategy,
        kb_context=kb_context,
        customer_memory=customer_memory,
        reply_memory=reply_memory,
        strict_prompt=retry_prompt,
    )
    retry_clean = normalize_customer_response(retry_reply, customer_name=customer_name)
    retry_validation = validate_response(answer=retry_clean, context_chunks=kb_context)
    if retry_validation.is_valid:
        return retry_clean, "validated_retry"
    return normalize_customer_response(SAFE_FALLBACK_RESPONSE, customer_name=customer_name), "fallback"


def _calculate_confidence(context_docs: List[str], reply_memory: List[str], reply: str) -> float:
    """Calculate overall pipeline confidence score."""
    confidence = 0.5
    if context_docs and len(context_docs) > 0:
        confidence += 0.15
    if len(context_docs) > 1:
        confidence += 0.10
    if reply_memory and len(reply_memory) > 0:
        confidence += 0.10
    if len(reply_memory) > 1:
        confidence += 0.05
    reply_text = (reply or "").strip()
    if len(reply_text) > 50:
        confidence += 0.10
    if len(reply_text) > 200:
        confidence += 0.05
    if len(reply_text) < 20:
        confidence -= 0.20
    return max(0.0, min(1.0, confidence))


def handle_customer_email(
    customer_email: str,
    subject: str,
    body: str,
    email_id: str = "",
    memory_service: Optional[CustomerMemoryAgent] = None,
) -> Dict[str, str]:
    """Execute the complete 16-stage V3 pipeline with persistent Customer Memory.
    
    1. Receive email
    2. Normalize email/message
    3. Resolve customer (CustomerProfile)
    4. Retrieve customer memory (CustomerMemory)
    5. Detect intent
    6. Detect emotion
    7. Retrieve ShopiFyX KB context
    8. Retrieve relevant previous reply memory
    9. Select response strategy
    10. Generate memory-aware response
    11. Validate response
    12. Make escalation decision
    13. Send email if approved
    14. Extract new customer memory
    15. Update customer memory
    16. Persist final conversation record
    """
    request_id = str(uuid4())[:8]
    if not email_id:
        email_id = request_id

    # Dependency injection: use provided memory service or default singleton
    mem_agent = memory_service or default_memory_agent

    try:
        # Step 1: Receive email
        LOGGER.info("[%s] [Stage 1/16] Received email from: %s | Subject: %s", request_id, customer_email, subject)

        # Step 2: Normalize email & message
        clean_email = normalize_email(customer_email)
        normalized_text = preprocess_text(body)
        customer_name = extract_customer_name(customer_email)
        LOGGER.info("[%s] [Stage 2/16] Normalized email: %s | Message len: %d chars", request_id, clean_email, len(normalized_text))

        # Step 3: Resolve customer
        try:
            profile: CustomerProfile = mem_agent.resolve_customer(clean_email, customer_name)
            customer_id = profile.customer_id
            LOGGER.info("[%s] [Stage 3/16] Resolved customer id=%s | Total interactions=%d", request_id, customer_id, profile.total_interactions)
        except Exception as exc:
            LOGGER.error("[%s] [Stage 3/16] Customer resolution fallback: %s", request_id, exc)
            profile = CustomerProfile(customer_id="0", email=clean_email, name=customer_name)
            customer_id = "0"

        # Step 4: Retrieve customer memory
        try:
            customer_memory: CustomerMemory = mem_agent.retrieve_memory(
                customer_id=customer_id,
                customer_email=clean_email,
                query_text=normalized_text,
            )
            LOGGER.info(
                "[%s] [Stage 4/16] Customer memory retrieved | Risk=%s | Open issues=%d | Turns=%d | Interests=%d",
                request_id,
                customer_memory.risk_level,
                len(customer_memory.open_issues),
                len(customer_memory.recent_conversations),
                len(customer_memory.interests),
            )
        except Exception as exc:
            LOGGER.error("[%s] [Stage 4/16] Memory retrieval fallback: %s", request_id, exc)
            customer_memory = CustomerMemory(profile=profile, risk_level="LOW", is_empty=True)

        # Step 5 & 6: Memory-aware Intent and Emotion Detection
        nlp_result = select_best_nlp_output(
            text=normalized_text,
            customer_memory=customer_memory,
        )
        intent = str(nlp_result.get("intent", "general_support")).strip()
        intent_confidence = float(nlp_result.get("intent_confidence", 0.5) or 0.5)
        emotion = str(nlp_result.get("emotion", "neutral")).strip()
        emotion_confidence = float(nlp_result.get("emotion_confidence", 0.5) or 0.5)
        reasoning_summary = str(nlp_result.get("reasoning_summary", "")).strip()
        memory_used = bool(nlp_result.get("memory_used", False))
        selected_model = str(nlp_result.get("selected_model", "unknown"))
        LOGGER.info(
            "[%s] [Stage 5-6/16] Detected intent: %s (%.2f) | emotion: %s (%.2f) | memory_used: %s | reason: %s",
            request_id,
            intent,
            intent_confidence,
            emotion,
            emotion_confidence,
            memory_used,
            reasoning_summary,
        )

        # Step 7: Retrieve ShopiFyX KB context (independent from customer memory)
        retrieval_query = clean_query_text(body)
        query = f"subject: {subject}\nmessage: {retrieval_query or normalized_text}"
        retrieval_result = retrieve_relevant_chunks(
            query=query,
            top_k=settings.rag_top_k,
            min_similarity=settings.rag_similarity_threshold,
            relaxed_fallback_k=settings.rag_relaxed_fallback_k,
            use_keyword_boost=settings.rag_keyword_boost,
        )
        retrieved_chunks = retrieval_result.chunks
        kb_context = [chunk.to_context_block() for chunk in retrieved_chunks]
        LOGGER.info("[%s] [Stage 7/16] Retrieved %d internal KB policy chunks", request_id, len(kb_context))

        # Step 8: Retrieve relevant previous reply memory
        similar_user_messages = retrieve_similar_user_messages(query=query, k=2)
        reply_memory: List[str] = (customer_memory.previous_replies or []) + similar_user_messages
        LOGGER.info("[%s] [Stage 8/16] Assembled %d relevant previous reply/interaction patterns", request_id, len(reply_memory))

        # Step 9: Select response strategy (memory & risk aware)
        strategy = select_strategy(intent=intent, emotion=emotion, customer_memory=customer_memory)
        LOGGER.info("[%s] [Stage 9/16] Selected response strategy: %s", request_id, strategy)

        # Step 10: Generate memory-aware response
        if not kb_context:
            LOGGER.warning("[%s] [Stage 10/16] No KB context found, using safe policy fallback", request_id)
            generated_reply = normalize_customer_response(SAFE_FALLBACK_RESPONSE, customer_name=customer_name)
        else:
            generated_reply, gen_status = _generate_validated_reply(
                current_message=normalized_text,
                intent=intent,
                emotion=emotion,
                strategy=strategy,
                kb_context=kb_context,
                customer_memory=customer_memory,
                reply_memory=reply_memory,
                customer_name=customer_name,
            )
            LOGGER.info("[%s] [Stage 10/16] Generated reply status: %s | len: %d chars", request_id, gen_status, len(generated_reply))
            LOGGER.debug("[%s] [Stage 10/16] Draft Reply Content:\n%s", request_id, generated_reply)

        # Step 11: Validate response & Safety middleware
        safe_reply, blocked, safety_reason = enforce_email_safety(answer=generated_reply, retrieved_context_chunks=kb_context)
        if blocked:
            LOGGER.warning("[%s] [Stage 11/16] Safety middleware enforced: %s", request_id, safety_reason)
        validation = validate_email_response(safe_reply, kb_context, intent, emotion)
        LOGGER.info(
            "[%s] [Stage 11/16] Response validation grounded=%s valid=%s | Issues=%s",
            request_id,
            validation.get("grounded"),
            validation.get("valid"),
            validation.get("issues") or "none",
        )

        # Step 12: Make escalation decision
        decision = decide_email_action(
            intent_confidence=intent_confidence,
            emotion_confidence=emotion_confidence,
            validation=validation,
            intent=intent,
            emotion=emotion,
            customer_message=normalized_text,
            generated_response=safe_reply,
            retrieved_context=kb_context,
            customer_risk_level=customer_memory.risk_level,
            customer_memory=customer_memory,
        )
        calculated_conf = _calculate_confidence(kb_context, reply_memory, safe_reply)
        decision_label = decision.get("decision", "HUMAN_REVIEW")
        LOGGER.info(
            "[%s] [Stage 12/16] Email decision: %s | CustomerRisk=%s | IntentConf=%.2f | Reason: %s",
            request_id,
            decision_label,
            customer_memory.risk_level,
            intent_confidence,
            decision.get("reason"),
        )

        # Step 13: Send email if approved (or trigger escalation)
        status = "failed"
        escalation_reason = ""

        if decision_label == "AUTO_SEND" and validation.get("valid", False):
            send_success = send_email(
                to_email=clean_email,
                subject=subject,
                body=safe_reply,
                use_reply_prefix=True,
                customer_name=customer_name,
            )
            if send_success:
                status = "replied"
                LOGGER.info("[%s] [Stage 13/16] Outbound email sent successfully to %s", request_id, clean_email)
            else:
                status = "failed"
                escalation_reason = "send_failed"
                LOGGER.error("[%s] [Stage 13/16] Outbound email dispatch failed to %s", request_id, clean_email)

        elif decision_label in {"HUMAN_REVIEW", "DO_NOT_SEND"}:
            status = "escalated"
            escalation_reason = decision.get("reason", "decision_escalated")
            LOGGER.warning("[%s] [Stage 13/16] Escalating interaction: %s", request_id, escalation_reason)
            try:
                escalate_to_human(
                    customer_email=clean_email,
                    subject=subject,
                    body=body,
                    reason=escalation_reason,
                    generated_reply=safe_reply,
                    confidence_score=calculated_conf,
                )
            except Exception as esc_err:
                LOGGER.warning("[%s] [Stage 13/16] Escalation dispatch notice failed: %s", request_id, esc_err)

        # Steps 14 & 15: Extract new customer memory and update memory state
        LOGGER.info("[%s] [Stage 14-15/16] Updating customer memory (status=%s)", request_id, status)
        try:
            mem_agent.update_memory(
                customer_id=customer_id,
                customer_email=clean_email,
                email_id=email_id,
                subject=subject,
                customer_message=body,
                normalized_message=normalized_text,
                intent=intent,
                intent_confidence=intent_confidence,
                emotion=emotion,
                emotion_confidence=emotion_confidence,
                strategy=strategy,
                reply=safe_reply,
                confidence=calculated_conf,
                status=status,
                escalation_reason=escalation_reason,
                selected_model=selected_model,
                retrieved_context_count=len(kb_context),
                similar_memory_count=len(reply_memory),
            )
            LOGGER.info("[%s] [Stage 15/16] Customer memory update completed", request_id)
        except Exception as mem_err:
            # Crucial: Memory update failure must never crash the pipeline or cause duplicate email dispatch
            LOGGER.error("[%s] [Stage 15/16] Non-blocking memory update error: %s", request_id, mem_err)

        # Step 16: Persist final conversation record & legacy logs
        try:
            save_email_record(
                sender=clean_email,
                subject=subject,
                body=body,
                intent=intent,
                emotion=emotion,
                reply=safe_reply,
                status=status,
                confidence=calculated_conf,
                escalation_reason=escalation_reason,
            )
            log_interaction({
                "customer_email": clean_email,
                "subject": subject,
                "intent": intent,
                "intent_confidence": intent_confidence,
                "emotion": emotion,
                "emotion_confidence": emotion_confidence,
                "strategy": strategy,
                "reply": safe_reply,
                "selected_model": selected_model,
            })
            LOGGER.info("[%s] [Stage 16/16] Interaction and email records persisted successfully", request_id)
        except Exception as log_err:
            LOGGER.warning("[%s] [Stage 16/16] Legacy log recording notice: %s", request_id, log_err)

        return {
            "status": status,
            "reply": safe_reply,
            "confidence": f"{calculated_conf:.2f}",
            "intent": intent,
            "emotion": emotion,
            "escalation_reason": escalation_reason,
        }

    except Exception as exc:
        LOGGER.exception("[%s] Unexpected exception in handle_customer_email: %s", request_id, exc)
        return {
            "status": "failed",
            "reply": "",
            "confidence": "0.00",
            "intent": "",
            "emotion": "",
            "escalation_reason": "processing_error",
        }


def process_email(
    email: dict,
    memory_service: Optional[CustomerMemoryAgent] = None,
) -> dict:
    """FastAPI endpoint handler for synchronous email processing with V3 Customer Memory."""
    sender = email.get("from") or email.get("sender") or email.get("customer_email") or ""
    subject = email.get("subject", "")
    body = email.get("body", "")
    email_id = email.get("id") or email.get("email_id") or str(uuid4())[:8]

    if not sender or not subject or not body:
        LOGGER.error("process_email: Missing required email fields")
        return {"status": "failed", "reply": "", "grounded": "False", "human_review_required": "True"}

    mem_agent = memory_service or default_memory_agent

    try:
        # Step 2: Normalize
        clean_email = normalize_email(sender)
        customer_name = extract_customer_name(sender)
        normalized_text = preprocess_text(body)

        # Step 3: Resolve customer
        profile = mem_agent.resolve_customer(clean_email, customer_name)
        customer_id = profile.customer_id

        # Step 4: Retrieve customer memory
        customer_memory = mem_agent.retrieve_memory(
            customer_id=customer_id,
            customer_email=clean_email,
            query_text=normalized_text,
        )

        # Steps 5 & 6: Memory-aware Intent & Emotion Detection
        nlp_result = select_best_nlp_output(
            text=normalized_text,
            customer_memory=customer_memory,
        )
        intent = str(nlp_result.get("intent", "general_support")).strip()
        intent_confidence = float(nlp_result.get("intent_confidence", 0.45) or 0.45)
        emotion = str(nlp_result.get("emotion", "neutral")).strip()
        emotion_confidence = float(nlp_result.get("emotion_confidence", 0.45) or 0.45)
        emotion_intensity = float(nlp_result.get("emotion_confidence", 0.5) or 0.5)

        # Step 7: KB context
        retrieval_query = clean_query_text(body)
        query = f"subject: {subject}\nmessage: {retrieval_query or normalized_text}"
        retrieval_result = retrieve_relevant_chunks(
            query=query,
            top_k=settings.rag_top_k,
            min_similarity=settings.rag_similarity_threshold,
            relaxed_fallback_k=settings.rag_relaxed_fallback_k,
            use_keyword_boost=settings.rag_keyword_boost,
        )
        retrieved_chunks = retrieval_result.chunks
        kb_context = [chunk.to_context_block() for chunk in retrieved_chunks]

        # Step 8: Reply memory
        similar_user_messages = retrieve_similar_user_messages(query=query, k=2)
        reply_memory: List[str] = (customer_memory.previous_replies or []) + similar_user_messages

        # Step 9: Strategy
        strategy = select_strategy(intent=intent, emotion=emotion, customer_memory=customer_memory)

        # Step 10: Generate memory-aware response
        if not kb_context:
            generated_reply = SAFE_FALLBACK_RESPONSE
        else:
            generated_reply, _ = _generate_validated_reply(
                current_message=normalized_text,
                intent=intent,
                emotion=emotion,
                strategy=strategy,
                kb_context=kb_context,
                customer_memory=customer_memory,
                reply_memory=reply_memory,
            )

        # Step 11: Validation & Safety
        safe_reply, blocked, safety_reason = enforce_email_safety(answer=generated_reply, retrieved_context_chunks=kb_context)
        if blocked:
            LOGGER.warning("process_email safety middleware replaced reply: %s", safety_reason)
        validation = validate_email_response(safe_reply, kb_context, intent, emotion)

        # Step 12: Decision
        decision = decide_email_action(
            intent_confidence=intent_confidence,
            emotion_confidence=emotion_confidence,
            validation=validation,
            intent=intent,
            emotion=emotion,
            customer_message=normalized_text,
            generated_response=safe_reply,
            retrieved_context=kb_context,
            customer_risk_level=customer_memory.risk_level,
            customer_memory=customer_memory,
        )

        calculated_conf = _calculate_confidence(kb_context, reply_memory, safe_reply)
        decision_label = decision.get("decision", "HUMAN_REVIEW")
        status = "replied"
        escalation_reason = ""

        # Step 13: Send or Escalate
        if decision_label != "AUTO_SEND":
            status = "escalated"
            escalation_reason = decision.get("reason", "decision_not_auto_send")
            LOGGER.warning("process_email routed to %s: %s", decision_label, escalation_reason)
        else:
            final_email = build_final_email(customer_name, body, intent, emotion, safe_reply)
            email_sent = send_email_reply(to=clean_email, subject=final_email["subject"], body=final_email["body"], customer_name=customer_name)
            status = "replied" if email_sent else "failed"

        # Steps 14 & 15: Extract & update memory
        try:
            mem_agent.update_memory(
                customer_id=customer_id,
                customer_email=clean_email,
                email_id=email_id,
                subject=subject,
                customer_message=body,
                normalized_message=normalized_text,
                intent=intent,
                intent_confidence=intent_confidence,
                emotion=emotion,
                emotion_confidence=emotion_confidence,
                strategy=strategy,
                reply=safe_reply,
                confidence=calculated_conf,
                status=status,
                escalation_reason=escalation_reason,
                selected_model="gemini",
                retrieved_context_count=len(kb_context),
                similar_memory_count=len(reply_memory),
            )
        except Exception as mem_err:
            LOGGER.error("process_email memory update error: %s", mem_err)

        # Step 16: Persist records
        try:
            save_email_record(
                sender=clean_email,
                subject=subject,
                body=body,
                intent=intent,
                emotion=emotion,
                reply=safe_reply,
                status=status,
                confidence=calculated_conf,
                escalation_reason=escalation_reason,
            )
            log_interaction({
                "customer_email": clean_email,
                "subject": subject,
                "intent": intent,
                "intent_confidence": intent_confidence,
                "emotion": emotion,
                "emotion_confidence": emotion_confidence,
                "strategy": strategy,
                "reply": safe_reply,
            })
        except Exception as log_err:
            LOGGER.warning("process_email legacy log error: %s", log_err)

        return {
            "status": status,
            "reply": safe_reply,
            "intent": intent,
            "intent_confidence": str(intent_confidence),
            "emotion": emotion,
            "emotion_intensity": str(emotion_intensity),
            "grounded": str(bool(validation.get("grounded", False))),
            "email_decision": decision_label,
            "human_review_required": str(bool(decision.get("requires_human", False))),
        }

    except Exception as exc:
        LOGGER.exception("process_email failed for sender=%s: %s", sender, exc)
        return {"status": "failed", "reply": "", "grounded": "False", "human_review_required": "True"}
