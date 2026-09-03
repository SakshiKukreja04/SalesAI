"""Customer Memory Agent (V3).

Central coordinator for persistent customer memory:
- Identity resolution
- Memory retrieval and prioritization
- Prompt formatting & budgeting
- Memory updates & structured extraction
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.memory.memory_formatter import format_customer_memory
from app.memory.memory_models import (
    CustomerMemory,
    CustomerProfile,
    FormattedMemoryContext,
)
from app.memory.memory_retriever import retrieve_customer_memory
from app.memory.memory_updater import update_customer_memory

LOGGER = logging.getLogger(__name__)


class CustomerMemoryAgent:
    """Dedicated Customer Memory Agent managing retrieval and persistence of customer context."""

    def __init__(self) -> None:
        LOGGER.info("CustomerMemoryAgent initialized")

    def resolve_customer(self, email: str, name: str = "") -> CustomerProfile:
        """Resolve or create a customer profile from incoming email."""
        from app.db.customer_memory import resolve_or_create_customer
        return resolve_or_create_customer(email=email, name=name)

    def retrieve_memory(
        self,
        customer_id: int,
        customer_email: str,
        intent: str = "",
        emotion: str = "",
        query_text: str = "",
    ) -> CustomerMemory:
        """Retrieve structured customer memory before response generation."""
        return retrieve_customer_memory(
            customer_id=customer_id,
            customer_email=customer_email,
            intent=intent,
            emotion=emotion,
            query_text=query_text,
        )

    def format_memory(
        self,
        memory: CustomerMemory,
        intent: str = "",
        current_message: str = "",
    ) -> FormattedMemoryContext:
        """Format memory into compact, prioritized prompt context."""
        return format_customer_memory(
            memory=memory,
            current_intent=intent,
            current_message=current_message,
        )

    def update_memory(
        self,
        customer_id: int,
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
        """Persist memory updates after processing."""
        return update_customer_memory(
            customer_id=customer_id,
            customer_email=customer_email,
            email_id=email_id,
            subject=subject,
            customer_message=customer_message,
            normalized_message=normalized_message,
            intent=intent,
            intent_confidence=intent_confidence,
            emotion=emotion,
            emotion_confidence=emotion_confidence,
            strategy=strategy,
            reply=reply,
            confidence=confidence,
            status=status,
            escalation_reason=escalation_reason,
            selected_model=selected_model,
            retrieved_context_count=retrieved_context_count,
            similar_memory_count=similar_memory_count,
        )


# Global singleton instance
memory_agent = CustomerMemoryAgent()
default_memory_agent = memory_agent
