"""Main multi-agent orchestration flow for customer support emails."""

import logging
from datetime import datetime, timezone
from typing import Dict
from uuid import uuid4

from app.agents.escalation import escalate_to_human, should_escalate
from app.agents.generator import generate_reply
from app.agents.strategy import select_strategy
from app.config import settings
from app.db.supabase_client import log_interaction, save_email_record
from app.email.safety_middleware import enforce_email_safety
from app.email.send_email import send_email, send_email_reply, extract_customer_name
from app.memory.reply_memory import store_reply_memory
from app.nlp.dual_llm import select_best_nlp_output
from app.nlp.emotion import detect_emotion
from app.nlp.intent import classify_intent
from app.nlp.preprocess import clean_query_text, preprocess_text
from app.rag.chroma_store import add_user_documents
from app.rag.prompt_builder import build_strict_context_prompt
from app.rag.response_validator import SAFE_FALLBACK_RESPONSE, validate_response
from app.rag.retrieval import retrieve_relevant_chunks, retrieve_similar_user_messages


LOGGER = logging.getLogger(__name__)


def _generate_validated_reply(
    strategy: str,
    intent: str,
    emotion: str,
    normalized_text: str,
    context_docs: list[str],
    similar_user_docs: list[str],
) -> str:
    """Generate reply under strict prompting with post-check and one retry."""
    strict_prompt = build_strict_context_prompt(
        user_query=normalized_text,
        retrieved_chunks=context_docs,
    )
    reply = generate_reply(
        strategy=strategy,
        intent=intent,
        emotion=emotion,
        context_docs=context_docs,
        similar_user_docs=similar_user_docs,
        customer_text=normalized_text,
        strict_prompt=strict_prompt,
    )

    validation = validate_response(answer=reply, context_chunks=context_docs)
    if validation.is_valid:
        return reply

    LOGGER.warning("Post-generation fact check failed: reason=%s", validation.reason)

    retry_prompt = (
        strict_prompt
        + "\n\n"
        + "IMPORTANT: The previous answer failed fact validation. "
        + "Use only exact facts in context and avoid unsupported numbers or timelines."
    )
    retry_reply = generate_reply(
        strategy=strategy,
        intent=intent,
        emotion=emotion,
        context_docs=context_docs,
        similar_user_docs=similar_user_docs,
        customer_text=normalized_text,
        strict_prompt=retry_prompt,
    )

    retry_validation = validate_response(answer=retry_reply, context_chunks=context_docs)
    if retry_validation.is_valid:
        return retry_reply

    LOGGER.warning("Retry fact check failed: reason=%s", retry_validation.reason)
    return SAFE_FALLBACK_RESPONSE


def _calculate_confidence(
    context_docs: list[str],
    similar_user_docs: list[str],
    reply: str,
) -> float:
    """Calculate confidence score for generated reply.
    
    Considers:
    - Quality of context documents (0.0-1.0 based on retrieval)
    - Similarity matches from user memory
    - Reply length and structure completeness
    
    Args:
        context_docs: Retrieved knowledge documents
        similar_user_docs: Similar past user messages
        reply: Generated reply text
    
    Returns:
        Confidence score between 0.0 and 1.0
    """
    confidence = 0.5  # Base confidence
    
    # Boost if we have relevant knowledge context
    if context_docs and len(context_docs) > 0:
        confidence += 0.15
    if len(context_docs) > 1:
        confidence += 0.10
    
    # Boost if we have similar user messages for reference
    if similar_user_docs and len(similar_user_docs) > 0:
        confidence += 0.10
    if len(similar_user_docs) > 1:
        confidence += 0.05
    
    # Boost if reply seems well-formed
    reply_text = (reply or "").strip()
    if len(reply_text) > 50:
        confidence += 0.10
    if len(reply_text) > 200:
        confidence += 0.05
    
    # Penalize if reply is too short or lacks detail
    if len(reply_text) < 20:
        confidence -= 0.20
    
    # Never exceed 1.0 or go below 0.0
    return max(0.0, min(1.0, confidence))


def handle_customer_email(customer_email: str, subject: str, body: str) -> Dict[str, str]:
    """Process one customer email through full NLP, RAG, strategy, and generation pipeline.
    
    Email Flow:
    1. Preprocess text
    2. Classify intent
    3. Detect emotion
    4. Retrieve knowledge context
    5. Retrieve similar user messages
    6. Generate reply
    7. Calculate confidence
    8. Check escalation criteria
    9. Either escalate or send reply + store memory
    10. Log to database
    
    Args:
        customer_email: Customer's email address
        subject: Email subject
        body: Email body text
    
    Returns:
        Dictionary with keys:
            - status: "replied" or "escalated"
            - reply: Generated or escalation reply
            - confidence: Confidence score (0.0-1.0)
            - intent: Classified intent
            - emotion: Detected emotion
            - escalation_reason: Reason for escalation (if applicable)
    """
    request_id = str(uuid4())[:8]
    
    try:
        LOGGER.info(
            "[%s] Processing email from %s: %s",
            request_id,
            customer_email,
            subject,
        )
        
        # Step 1: Preprocess and analyze
        normalized_text = preprocess_text(body)
        
        # Step 2-3: Dual-LLM intent and emotion detection with automatic selection
        nlp_result = select_best_nlp_output(normalized_text)
        intent = nlp_result.get("intent", "Inquiry")
        intent_confidence = float(nlp_result.get("intent_confidence", 0.5))
        emotion = nlp_result.get("emotion", "neutral")
        emotion_confidence = float(nlp_result.get("emotion_confidence", 0.5))
        selected_model = nlp_result.get("selected_model", "unknown")
        
        LOGGER.debug(
            "[%s] NLP Results: intent=%s (%.2f), emotion=%s (%.2f) [selected=%s]",
            request_id,
            intent,
            intent_confidence,
            emotion,
            emotion_confidence,
            selected_model,
        )
        
        # Step 4-5: Retrieve context from RAG
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
        context_docs = [chunk.to_context_block() for chunk in retrieved_chunks]
        similar_user_docs = retrieve_similar_user_messages(query=query, k=2)
        
        LOGGER.debug(
            "[%s] RAG Retrieval: %d knowledge chunks, %d similar messages",
            request_id,
            len(retrieved_chunks),
            len(similar_user_docs),
        )

        if not context_docs:
            LOGGER.warning("[%s] No relevant chunks above threshold, using safe fallback", request_id)
            reply = SAFE_FALLBACK_RESPONSE
        else:
            if retrieval_result.fallback_relaxed:
                LOGGER.warning("[%s] Using relaxed retrieval fallback chunks for generation", request_id)
            reply = _generate_validated_reply(
                strategy=select_strategy(intent=intent, emotion=emotion),
                intent=intent,
                emotion=emotion,
                normalized_text=normalized_text,
                context_docs=context_docs,
                similar_user_docs=similar_user_docs,
            )
        
        # Step 6: Strategy selection
        strategy = select_strategy(intent=intent, emotion=emotion)

        LOGGER.info("[%s] RAG Debug | query=%r", request_id, query)
        for idx, chunk in enumerate(retrieved_chunks, start=1):
            LOGGER.info(
                "[%s] Chunk #%d score=%.3f source=%s topic=%s version=%s",
                request_id,
                idx,
                chunk.score,
                chunk.source_file,
                chunk.topic,
                chunk.version,
            )
        
        # Step 8: Calculate confidence
        confidence_score = _calculate_confidence(
            context_docs=context_docs,
            similar_user_docs=similar_user_docs,
            reply=reply,
        )
        
        LOGGER.info(
            "[%s] Generated reply (confidence=%.2f, strategy=%s)",
            request_id,
            confidence_score,
            strategy,
        )
        
        # Step 9: Check escalation criteria
        should_escalate_email, escalation_reason = should_escalate(
            confidence_score=confidence_score,
            intent=intent,
            emotion=emotion,
        )
        
        if should_escalate_email:
            # Escalate to human support
            LOGGER.warning(
                "[%s] Escalating email: %s (confidence=%.2f)",
                request_id,
                escalation_reason,
                confidence_score,
            )
            
            escalate_to_human(
                customer_email=customer_email,
                subject=subject,
                body=body,
                reason=escalation_reason,
                generated_reply=reply,
                confidence_score=confidence_score,
            )
            
            # Step 10: Save escalation record
            save_email_record(
                sender=customer_email,
                subject=subject,
                body=body,
                intent=intent,
                emotion=emotion,
                reply=reply,
                status="escalated",
                confidence=confidence_score,
                escalation_reason=escalation_reason,
            )
            
            log_interaction(
                {
                    "customer_email": customer_email,
                    "subject": subject,
                    "intent": intent,
                    "intent_confidence": intent_confidence,
                    "emotion": emotion,
                    "emotion_confidence": emotion_confidence,
                    "strategy": strategy,
                    "reply": reply,
                    "selected_model": selected_model,
                }
            )
            
            return {
                "status": "escalated",
                "reply": reply,
                "confidence": f"{confidence_score:.2f}",
                "intent": intent,
                "emotion": emotion,
                "escalation_reason": escalation_reason,
            }
        
        else:
            # Send reply to customer
            LOGGER.info("[%s] Sending reply to customer", request_id)
            
            safe_reply, blocked, safety_reason = enforce_email_safety(
                answer=reply,
                retrieved_context_chunks=context_docs,
            )
            if blocked:
                LOGGER.warning("[%s] SMTP safety middleware replaced reply: %s", request_id, safety_reason)

            send_success = send_email(
                to_email=customer_email,
                subject=subject,
                body=safe_reply,
                use_reply_prefix=True,
            )
            
            if not send_success:
                LOGGER.error("[%s] Failed to send email", request_id)
                save_email_record(
                    sender=customer_email,
                    subject=subject,
                    body=body,
                    intent=intent,
                    emotion=emotion,
                    reply=safe_reply,
                    status="failed",
                    confidence=confidence_score,
                )
                return {
                    "status": "failed",
                    "reply": "",
                    "confidence": f"{confidence_score:.2f}",
                    "intent": intent,
                    "emotion": emotion,
                    "escalation_reason": "send_failed",
                }
            
            # Store user message in memory
            add_user_documents(
                documents=[normalized_text],
                ids=[str(uuid4())],
                metadatas=[
                    {
                        "source": "user_message",
                        "customer_email": customer_email,
                        "subject": subject,
                        "intent": intent,
                        "emotion": emotion,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ],
            )
            
            # Store reply in memory for future reference
            store_reply_memory(
                customer_email=customer_email,
                generated_reply=safe_reply,
                intent=intent,
                emotion=emotion,
            )
            
            # Save successful reply record
            save_email_record(
                sender=customer_email,
                subject=subject,
                body=body,
                intent=intent,
                emotion=emotion,
                reply=safe_reply,
                status="replied",
                confidence=confidence_score,
            )
            
            log_interaction(
                {
                    "customer_email": customer_email,
                    "subject": subject,
                    "intent": intent,
                    "intent_confidence": intent_confidence,
                    "emotion": emotion,
                    "emotion_confidence": emotion_confidence,
                    "strategy": strategy,
                    "reply": safe_reply,
                    "selected_model": selected_model,
                }
            )

            LOGGER.info("[%s] Final answer (post-safety): %s", request_id, safe_reply)
            
            LOGGER.info(
                "[%s] Email processed successfully (status=replied)",
                request_id,
            )
            
            return {
                "status": "replied",
                "reply": safe_reply,
                "confidence": f"{confidence_score:.2f}",
                "intent": intent,
                "emotion": emotion,
                "escalation_reason": "",
            }
    
    except Exception as exc:
        LOGGER.exception("[%s] Unexpected error processing email: %s", request_id, exc)
        
        # Try to log the failure
        try:
            save_email_record(
                sender=customer_email,
                subject=subject,
                body=body,
                intent="unknown",
                emotion="unknown",
                reply="",
                status="failed",
                confidence=0.0,
                escalation_reason="processing_error",
            )
        except Exception as log_exc:
            LOGGER.error("Failed to log error: %s", log_exc)
        
        return {
            "status": "failed",
            "reply": "",
            "confidence": "0.00",
            "intent": "",
            "emotion": "",
            "escalation_reason": "processing_error",
        }


def process_email(email: dict) -> dict:
    """New orchestrator flow: generate, send, memory, save record."""
    sender = email.get("from") or email.get("sender") or ""
    subject = email.get("subject", "")
    body = email.get("body", "")

    if not sender or not subject or not body:
        LOGGER.error("process_email: Missing required email fields")
        return {"status": "failed", "reply": ""}

    try:
        # Extract customer name from email header
        customer_name = extract_customer_name(sender)
        
        normalized_text = preprocess_text(body)
        intent_data = classify_intent(normalized_text)
        intent = intent_data.get("intent", "unknown")
        emotion_data = detect_emotion(normalized_text)
        emotion = emotion_data.get("emotion", "unknown")

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
        context_docs = [chunk.to_context_block() for chunk in retrieved_chunks]
        similar_user_docs = retrieve_similar_user_messages(query=query, k=2)

        strategy = select_strategy(intent=intent, emotion=emotion)
        if not context_docs:
            generated_reply = SAFE_FALLBACK_RESPONSE
        else:
            if retrieval_result.fallback_relaxed:
                LOGGER.warning("process_email using relaxed retrieval fallback chunks for generation")
            generated_reply = _generate_validated_reply(
                strategy=strategy,
                intent=intent,
                emotion=emotion,
                normalized_text=normalized_text,
                context_docs=context_docs,
                similar_user_docs=similar_user_docs,
            )

        safe_reply, blocked, safety_reason = enforce_email_safety(
            answer=generated_reply,
            retrieved_context_chunks=context_docs,
        )
        if blocked:
            LOGGER.warning("process_email SMTP safety middleware replaced reply: %s", safety_reason)

        # Send via SMTP using dedicated helper with customer name
        email_sent = send_email_reply(
            to=sender,
            subject=subject,
            body=safe_reply,
            customer_name=customer_name,
        )

        status = "replied" if email_sent else "failed"

        if email_sent:
            LOGGER.info("Email sent successfully to %s (%s)", sender, customer_name)
            store_reply_memory(
                customer_email=sender,
                generated_reply=safe_reply,
                intent=intent,
                emotion=emotion,
            )
            LOGGER.info("Reply stored in memory")
        else:
            LOGGER.error("Email send failed for %s (%s)", sender, customer_name)

        save_email_record(
            sender=sender,
            subject=subject,
            body=body,
            intent=intent,
            emotion=emotion,
            reply=safe_reply,
            status=status,
            confidence=_calculate_confidence(
                context_docs=context_docs,
                similar_user_docs=similar_user_docs,
                reply=safe_reply,
            ),
        )
        LOGGER.info("Email record saved with status=%s", status)

        log_interaction(
            {
                "customer_email": sender,
                "subject": subject,
                "intent": intent,
                "intent_confidence": intent_data.get("confidence", 0.0),
                "emotion": emotion,
                "emotion_confidence": emotion_data.get("confidence", 0.0),
                "strategy": strategy,
                "reply": safe_reply,
            }
        )

        LOGGER.info("RAG Debug | query=%r", query)
        for idx, chunk in enumerate(retrieved_chunks, start=1):
            LOGGER.info(
                "Chunk #%d score=%.3f source=%s topic=%s version=%s",
                idx,
                chunk.score,
                chunk.source_file,
                chunk.topic,
                chunk.version,
            )
        LOGGER.info("Final answer (post-safety): %s", safe_reply)

        return {"status": status, "reply": safe_reply}

    except Exception as exc:
        LOGGER.exception("process_email failed for sender=%s: %s", sender, exc)
        try:
            save_email_record(
                sender=sender,
                subject=subject,
                body=body,
                intent=intent if "intent" in locals() else "unknown",
                emotion=emotion if "emotion" in locals() else "unknown",
                reply="",
                status="failed",
                confidence=0.0,
            )
        except Exception as log_exc:
            LOGGER.error("Failed to save failed email record: %s", log_exc)

        return {"status": "failed", "reply": ""}
