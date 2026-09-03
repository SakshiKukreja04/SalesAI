"""Pydantic models and dataclasses for Customer Memory Agent (V3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


@dataclass
class CustomerProfile:
    """Customer entity representation."""

    customer_id: Union[str, int]
    email: str
    name: str = ""
    total_interactions: int = 0
    first_contact_at: Optional[datetime] = None
    last_contact_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "customer_id": str(self.customer_id),
            "email": self.email,
            "name": self.name,
            "total_interactions": self.total_interactions,
            "first_contact_at": self.first_contact_at.isoformat() if self.first_contact_at else None,
            "last_contact_at": self.last_contact_at.isoformat() if self.last_contact_at else None,
        }


@dataclass
class CustomerIssue:
    """Tracked customer issue or complaint."""

    id: Optional[Union[str, int]] = None
    customer_id: Union[str, int] = ""
    issue_title: str = ""
    description: str = ""
    status: str = "open"  # open, resolved, escalated
    priority: str = "medium"  # low, medium, high, urgent
    resolution_notes: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id) if self.id else None,
            "customer_id": str(self.customer_id),
            "issue_title": self.issue_title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "resolution_notes": self.resolution_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class CustomerInterest:
    """Tracked customer product preference or interest."""

    id: Optional[Union[str, int]] = None
    customer_id: Union[str, int] = ""
    product_name: str = ""
    interest_status: str = "active"  # active, converted, closed
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id) if self.id else None,
            "customer_id": str(self.customer_id),
            "product_name": self.product_name,
            "interest_status": self.interest_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class ConversationRecord:
    """Conversation-level turn record."""

    id: Optional[Union[str, int]] = None
    customer_id: Union[str, int] = ""
    email_id: str = ""
    subject: str = ""
    customer_message: str = ""
    normalized_message: str = ""
    intent: str = "general_support"
    intent_confidence: float = 0.5
    emotion: str = "neutral"
    emotion_confidence: float = 0.5
    strategy: str = "general_helpful"
    generated_reply: str = ""
    confidence: float = 0.5
    status: str = "replied"  # replied, escalated, failed
    escalation_reason: str = ""
    selected_model: str = "gemini"
    retrieved_context_count: int = 0
    similar_memory_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id) if self.id else None,
            "customer_id": str(self.customer_id),
            "email_id": self.email_id,
            "subject": self.subject,
            "customer_message": self.customer_message,
            "normalized_message": self.normalized_message,
            "intent": self.intent,
            "intent_confidence": self.intent_confidence,
            "emotion": self.emotion,
            "emotion_confidence": self.emotion_confidence,
            "strategy": self.strategy,
            "generated_reply": self.generated_reply,
            "confidence": self.confidence,
            "status": self.status,
            "escalation_reason": self.escalation_reason,
            "selected_model": self.selected_model,
            "retrieved_context_count": self.retrieved_context_count,
            "similar_memory_count": self.similar_memory_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class CustomerMemory:
    """Aggregated customer context retrieved before response generation."""

    profile: Optional[CustomerProfile] = None
    recent_conversations: List[ConversationRecord] = field(default_factory=list)
    open_issues: List[CustomerIssue] = field(default_factory=list)
    resolved_issues: List[CustomerIssue] = field(default_factory=list)
    interests: List[CustomerInterest] = field(default_factory=list)
    relevant_interactions: List[Dict[str, Any]] = field(default_factory=list)
    previous_replies: List[str] = field(default_factory=list)
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, ESCALATE_IMMEDIATELY
    sentiment_trend: float = 0.0  # -1.0 (worsening) to +1.0 (improving)
    repeat_issue_detected: bool = False
    repeat_issue_intent: Optional[str] = None
    is_empty: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile": self.profile.to_dict() if self.profile else None,
            "recent_conversations": [c.to_dict() for c in self.recent_conversations],
            "open_issues": [i.to_dict() for i in self.open_issues],
            "resolved_issues": [i.to_dict() for i in self.resolved_issues],
            "interests": [item.to_dict() for item in self.interests],
            "relevant_interactions": self.relevant_interactions,
            "previous_replies": self.previous_replies,
            "risk_level": self.risk_level,
            "sentiment_trend": self.sentiment_trend,
            "repeat_issue_detected": self.repeat_issue_detected,
            "repeat_issue_intent": self.repeat_issue_intent,
            "is_empty": self.is_empty,
        }


class MemoryUpdate(BaseModel):
    """Strict Pydantic schema for durable customer memory extraction."""

    customer_name: Optional[str] = None
    products: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    issue: Optional[str] = None
    issue_status: Optional[str] = None  # open, resolved, escalated
    issue_priority: Optional[str] = None  # low, medium, high, urgent
    issue_resolved: bool = False
    interaction_facts: List[str] = Field(default_factory=list)
    # Backward compatibility aliases/fields
    products_mentioned: List[str] = Field(default_factory=list)
    products_interested: List[str] = Field(default_factory=list)
    issue_detected: bool = False
    issue_title: Optional[str] = None
    issue_description: Optional[str] = None


# Alias for backward compatibility
MemoryExtractionResult = MemoryUpdate


@dataclass
class FormattedMemoryContext:
    """Compact prompt-ready memory context adhering to memory budget."""

    profile_text: str = ""
    recent_history_text: str = ""
    open_issues_text: str = ""
    product_interests_text: str = ""
    relevant_interactions_text: str = ""
    reply_patterns_text: str = ""
    full_context_text: str = ""
