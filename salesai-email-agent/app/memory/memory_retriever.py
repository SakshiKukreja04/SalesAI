"""Customer Memory Retrieval module.

Retrieves profile, recent conversations, open/resolved issues, product interests,
and semantically relevant previous interactions to assemble a structured CustomerMemory.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.db.customer_memory import (
    get_customer_conversations,
    get_customer_interests,
    get_customer_issues,
    resolve_or_create_customer,
)
from app.memory.memory_models import (
    ConversationRecord,
    CustomerInterest,
    CustomerIssue,
    CustomerMemory,
    CustomerProfile,
)

LOGGER = logging.getLogger(__name__)

# Emotion valence mapping for sentiment trend calculation
EMOTION_VALENCE = {
    "happy": 1.0,
    "satisfied": 0.8,
    "positive": 0.8,
    "neutral": 0.0,
    "confused": -0.2,
    "worried": -0.4,
    "disappointed": -0.5,
    "frustrated": -0.7,
    "angry": -0.9,
    "urgent": -0.7,
}


def _calculate_sentiment_trend(conversations: List[ConversationRecord]) -> float:
    """Calculate emotional trajectory over recent conversations.
    
    Returns float from -1.0 (strongly worsening / negative) to +1.0 (positive / improving).
    """
    if not conversations:
        return 0.0

    scores = []
    # conversations are ordered newest first, reverse to chronological for trend
    for conv in reversed(conversations[-6:]):
        emotion = (conv.emotion or "neutral").strip().lower()
        scores.append(EMOTION_VALENCE.get(emotion, 0.0))

    if not scores:
        return 0.0

    if len(scores) == 1:
        return scores[0]

    # Weighted moving average favoring recent turns
    weights = [0.5 + 0.5 * (i / len(scores)) for i in range(len(scores))]
    weighted_sum = sum(s * w for s, w in zip(scores, weights))
    total_weight = sum(weights)
    
    return max(-1.0, min(1.0, weighted_sum / total_weight if total_weight else 0.0))


def _detect_repeat_issues(
    current_intent: str,
    open_issues: List[CustomerIssue],
    recent_conversations: List[ConversationRecord],
) -> tuple[bool, Optional[str]]:
    """Check if the current intent represents a repeat or unresolved problem."""
    clean_intent = (current_intent or "").strip().lower()
    if not clean_intent:
        return False, None

    # Check against open issues
    for issue in open_issues:
        if clean_intent in issue.issue_title.lower() or issue.issue_title.lower() in clean_intent:
            return True, issue.issue_title

    # Check if the intent occurred >= 2 times in recent turns
    intent_count = sum(1 for c in recent_conversations if c.intent.strip().lower() == clean_intent)
    if intent_count >= 2:
        return True, current_intent

    return False, None


def _calculate_risk_level(
    open_issues: List[CustomerIssue],
    recent_conversations: List[ConversationRecord],
    sentiment_trend: float,
    current_emotion: str,
    repeat_issue_detected: bool,
) -> str:
    """Compute customer risk level for escalation and threshold adaptation.
    
    Returns: 'LOW' | 'MEDIUM' | 'HIGH' | 'ESCALATE_IMMEDIATELY'
    """
    clean_emotion = (current_emotion or "neutral").strip().lower()
    open_count = len(open_issues)

    if (open_count >= 2 and clean_emotion in {"angry", "urgent"}) or (sentiment_trend < -0.7 and clean_emotion == "angry"):
        return "ESCALATE_IMMEDIATELY"

    if repeat_issue_detected or clean_emotion in {"angry", "urgent"} or open_count >= 1 or sentiment_trend < -0.4:
        return "HIGH"

    if clean_emotion in {"frustrated", "worried", "disappointed"} or sentiment_trend < -0.1:
        return "MEDIUM"

    return "LOW"


def _retrieve_semantic_interactions(
    customer_email: str,
    query_text: str,
    k: int = 3,
) -> List[Dict[str, Any]]:
    """Retrieve semantically similar past customer interactions from ChromaDB."""
    if not query_text or not customer_email:
        return []

    try:
        from app.rag.chroma_store import ensure_user_collection
        user_col = ensure_user_collection()
        results = user_col.query(
            query_texts=[query_text],
            n_results=k * 2,
            where={"customer_email": customer_email.lower().strip()},
        )

        docs = results.get("documents", [[]])[0] if results.get("documents") else []
        metas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []

        interactions = []
        for d, m in zip(docs, metas):
            interactions.append({
                "message": d,
                "intent": m.get("intent", ""),
                "emotion": m.get("emotion", ""),
                "timestamp": m.get("timestamp", ""),
                "subject": m.get("subject", ""),
            })
        return interactions[:k]
    except Exception as exc:
        LOGGER.debug("Semantic interaction retrieval skipped: %s", exc)
        return []


def _retrieve_relevant_previous_replies(
    customer_email: str,
    query_text: str,
    k: int = 2,
) -> List[str]:
    """Retrieve semantically relevant previous responses from reply-memory ChromaDB."""
    if not query_text:
        return []

    try:
        from app.rag.chroma_store import ensure_reply_collection
        reply_col = ensure_reply_collection()
        where_filter = {"customer_email": customer_email.lower().strip()} if customer_email else None
        
        query_kwargs = {"query_texts": [query_text], "n_results": k}
        if where_filter:
            try:
                results = reply_col.query(**query_kwargs, where=where_filter)
            except Exception:
                results = reply_col.query(**query_kwargs)
        else:
            results = reply_col.query(**query_kwargs)

        docs = results.get("documents", [[]])[0] if results.get("documents") else []
        return [str(d) for d in docs if d]
    except Exception as exc:
        LOGGER.debug("Relevant reply retrieval skipped: %s", exc)
        return []


def retrieve_customer_memory(
    customer_id: int,
    customer_email: str,
    intent: str = "",
    emotion: str = "",
    query_text: str = "",
) -> CustomerMemory:
    """Retrieve comprehensive customer memory before response generation.
    
    Args:
        customer_id: Resolved customer ID
        customer_email: Normalized customer email
        intent: Classified or predicted intent (optional, for prioritization)
        emotion: Detected or predicted emotion (optional, for risk calculation)
        query_text: Customer message text for semantic matching
    
    Returns:
        Structured CustomerMemory object with profile, history, issues, interests, and risk level.
    """
    start_time = time.time()
    try:
        # 1. Profile
        profile: Optional[CustomerProfile] = None
        if customer_id:
            from app.db.customer_memory import get_customer_by_id
            profile = get_customer_by_id(customer_id)
        if not profile and customer_email:
            profile = resolve_or_create_customer(customer_email)

        # 2. Recent Conversations
        recent_conversations = get_customer_conversations(customer_id=profile.customer_id if profile else customer_id, limit=8)

        # 3. Customer Issues (Open & Resolved)
        open_issues = get_customer_issues(customer_id=profile.customer_id if profile else customer_id, status="open")
        resolved_issues = get_customer_issues(customer_id=profile.customer_id if profile else customer_id, status="resolved")

        # 4. Product Interests
        interests = get_customer_interests(customer_id=profile.customer_id if profile else customer_id, status="active")

        # 5. Semantic interactions & previous replies
        semantic_interactions = _retrieve_semantic_interactions(customer_email, query_text, k=2)
        previous_replies = _retrieve_relevant_previous_replies(customer_email, query_text, k=2)

        # 6. Trend & Risk calculations
        sentiment_trend = _calculate_sentiment_trend(recent_conversations)
        repeat_detected, repeat_intent = _detect_repeat_issues(intent, open_issues, recent_conversations)
        risk_level = _calculate_risk_level(open_issues, recent_conversations, sentiment_trend, emotion, repeat_detected)

        is_empty = (
            not profile
            and not recent_conversations
            and not open_issues
            and not interests
            and not semantic_interactions
        )

        memory = CustomerMemory(
            profile=profile,
            recent_conversations=recent_conversations,
            open_issues=open_issues,
            resolved_issues=resolved_issues,
            interests=interests,
            relevant_interactions=semantic_interactions,
            previous_replies=previous_replies,
            risk_level=risk_level,
            sentiment_trend=sentiment_trend,
            repeat_issue_detected=repeat_detected,
            repeat_issue_intent=repeat_intent,
            is_empty=is_empty,
        )

        duration_ms = (time.time() - start_time) * 1000
        LOGGER.info(
            "Customer memory retrieved in %.1fms | email=%s | conversations=%d | open_issues=%d | interests=%d | risk=%s",
            duration_ms,
            customer_email,
            len(recent_conversations),
            len(open_issues),
            len(interests),
            risk_level,
        )
        return memory

    except Exception as exc:
        LOGGER.error("Failed to retrieve customer memory for %s: %s", customer_email, exc)
        return CustomerMemory(
            profile=CustomerProfile(customer_id=customer_id, email=customer_email, name="Valued Customer"),
            risk_level="LOW",
            is_empty=True,
        )
