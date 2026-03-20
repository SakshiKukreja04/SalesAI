"""Main multi-agent orchestration flow for customer support emails."""

from typing import Dict

from app.agents.generator import generate_reply
from app.agents.strategy import select_strategy
from app.db.supabase_client import log_interaction
from app.nlp.emotion import detect_emotion
from app.nlp.intent import classify_intent
from app.nlp.preprocess import preprocess_text
from app.rag.retrieval import retrieve_top_k


def handle_customer_email(customer_email: str, subject: str, body: str) -> Dict[str, str]:
    """Process one customer email through NLP, RAG, strategy, and generation."""
    normalized_text = preprocess_text(body)
    intent = classify_intent(normalized_text)
    emotion = detect_emotion(normalized_text)

    query = f"subject: {subject}\nmessage: {normalized_text}"
    context_docs = retrieve_top_k(query=query, k=2)

    strategy = select_strategy(intent=intent, emotion=emotion)
    reply = generate_reply(
        strategy=strategy,
        intent=intent,
        emotion=emotion,
        context_docs=context_docs,
        customer_text=normalized_text,
    )

    log_interaction(
        {
            "customer_email": customer_email,
            "subject": subject,
            "intent": intent,
            "emotion": emotion,
            "strategy": strategy,
            "reply": reply,
        }
    )

    return {
        "intent": intent,
        "emotion": emotion,
        "strategy": strategy,
        "reply": reply,
    }
