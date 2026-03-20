"""Response generation module.

Builds customer-facing replies using selected strategy and retrieved knowledge.
A Gemini placeholder is included for future LLM-powered generation.
"""

from typing import List

from app.config import settings


def _gemini_generate_placeholder(prompt: str) -> str:
    """Placeholder for Gemini response generation call."""
    if settings.gemini_api_key:
        # Replace this with a real Gemini API request.
        pass
    return f"[PLACEHOLDER GEMINI REPLY]\n{prompt}"


def generate_reply(strategy: str, intent: str, emotion: str, context_docs: List[str], customer_text: str) -> str:
    """Generate a reply text from strategy, NLP outputs, and retrieved context."""
    context_block = "\n\n".join(context_docs) if context_docs else "No internal policy context found."

    prompt = (
        f"Strategy: {strategy}\n"
        f"Intent: {intent}\n"
        f"Emotion: {emotion}\n"
        f"Customer message: {customer_text}\n\n"
        f"Relevant policy context:\n{context_block}\n\n"
        "Write a short, clear, professional support email response."
    )

    return _gemini_generate_placeholder(prompt)
