"""Reply memory storage in ChromaDB for historical reply tracking.

Stores generated replies with metadata for future pattern matching and
consistency improvement.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.rag.chroma_store import add_reply_documents


LOGGER = logging.getLogger(__name__)


def store_reply_memory(
    customer_email: str,
    generated_reply: str,
    intent: str,
    emotion: str,
) -> bool:
    """Store generated reply in ChromaDB for future retrieval and pattern matching.
    
    Args:
        customer_email: Email address of the customer
        generated_reply: The generated reply text
        intent: Classified intent (e.g., "Refund Request", "Complaint")
        emotion: Detected emotion (e.g., "angry", "happy")
    
    Returns:
        True if storage succeeded, False otherwise
    """
    try:
        reply_id = str(uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        documents = [generated_reply]
        ids = [reply_id]
        metadatas = [
            {
                "customer_email": customer_email,
                "intent": intent,
                "emotion": emotion,
                "timestamp": timestamp,
                "reply_type": "generated",
            }
        ]
        
        add_reply_documents(documents=documents, ids=ids, metadatas=metadatas)
        LOGGER.info(
            "Reply stored in memory (id=%s, email=%s, intent=%s, emotion=%s)",
            reply_id,
            customer_email,
            intent,
            emotion,
        )
        return True
        
    except Exception as exc:
        LOGGER.error("Failed to store reply in memory: %s", exc)
        return False
