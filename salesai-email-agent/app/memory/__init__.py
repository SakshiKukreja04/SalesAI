"""Memory package for SalesAI V3.

Provides persistent Customer Memory Agent and ChromaDB reply memory.
"""

from app.memory.memory_models import (
    ConversationRecord,
    CustomerInterest,
    CustomerIssue,
    CustomerMemory,
    CustomerProfile,
    FormattedMemoryContext,
    MemoryExtractionResult,
)

__all__ = [
    "CustomerProfile",
    "CustomerIssue",
    "CustomerInterest",
    "ConversationRecord",
    "CustomerMemory",
    "MemoryExtractionResult",
    "FormattedMemoryContext",
    "CustomerMemoryAgent",
    "memory_agent",
    "retrieve_customer_memory",
    "format_customer_memory",
    "update_customer_memory",
    "extract_memory_from_turn",
    "store_reply_memory",
]


def __getattr__(name: str):
    if name in {"CustomerMemoryAgent", "memory_agent"}:
        from app.memory.customer_memory import CustomerMemoryAgent, memory_agent
        return memory_agent if name == "memory_agent" else CustomerMemoryAgent
    elif name == "retrieve_customer_memory":
        from app.memory.memory_retriever import retrieve_customer_memory
        return retrieve_customer_memory
    elif name == "format_customer_memory":
        from app.memory.memory_formatter import format_customer_memory
        return format_customer_memory
    elif name in {"update_customer_memory", "extract_memory_from_turn"}:
        from app.memory.memory_updater import extract_memory_from_turn, update_customer_memory
        return update_customer_memory if name == "update_customer_memory" else extract_memory_from_turn
    elif name == "store_reply_memory":
        from app.memory.reply_memory import store_reply_memory
        return store_reply_memory
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
