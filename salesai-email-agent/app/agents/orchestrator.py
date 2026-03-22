"""Main multi-agent orchestration flow for customer support emails."""

from datetime import datetime, timezone
from typing import Dict
from uuid import uuid4

from app.agents.generator import generate_reply
from app.agents.strategy import select_strategy
from app.db.supabase_client import log_interaction
from app.nlp.emotion import detect_emotion
from app.nlp.intent import classify_intent
from app.nlp.preprocess import preprocess_text
from app.rag.chroma_store import add_user_documents
from app.rag.retrieval import retrieve_similar_user_messages, retrieve_top_k


def handle_customer_email(customer_email: str, subject: str, body: str) -> Dict[str, str]:
    """Process one customer email through NLP, RAG, strategy, and generation."""
    normalized_text = preprocess_text(body)
    intent_data = classify_intent(normalized_text)
    intent = intent_data["intent"]
    intent_confidence = intent_data["confidence"]
    emotion_data = detect_emotion(normalized_text)
    emotion = emotion_data["emotion"]
    emotion_confidence = emotion_data["confidence"]

    query = f"subject: {subject}\nmessage: {normalized_text}"
    context_docs = retrieve_top_k(query=query, k=2)
    similar_user_docs = retrieve_similar_user_messages(query=query, k=2)

    strategy = select_strategy(intent=intent, emotion=emotion)
    reply = generate_reply(
        strategy=strategy,
        intent=intent,
        emotion=emotion,
        context_docs=context_docs,
        similar_user_docs=similar_user_docs,
        customer_text=normalized_text,
    )

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
        }
    )

    return {
        "intent": intent,
        "intent_confidence": intent_confidence,
        "emotion": emotion,
        "emotion_confidence": emotion_confidence,
        "strategy": strategy,
        "reply": reply,
    }
