"""Response generation module.

Builds customer-facing replies using selected strategy and retrieved knowledge.
A Gemini generator is used when configured, with deterministic fallback output.
"""

import logging
from typing import List

from app.config import settings


LOGGER = logging.getLogger(__name__)


def _model_candidates() -> List[str]:
    """Build ordered candidate model names from settings and Flash-first fallbacks."""
    configured = (settings.gemini_model or "").strip()
    candidates = [
        configured,
        "gemini-2.0-flash",
        "models/gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "models/gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "models/gemini-1.5-flash",
    ]
    return [name for name in candidates if name]


def _list_supported_models(genai_module: object) -> List[str]:
    """Return model names that support generateContent, if listing succeeds."""
    try:
        supported: List[str] = []
        for model in genai_module.list_models():
            methods = getattr(model, "supported_generation_methods", []) or []
            if "generateContent" in methods:
                name = getattr(model, "name", "")
                if name:
                    supported.append(name.replace("models/", ""))
        return supported
    except Exception:
        return []


def _gemini_generate(prompt: str) -> str:
    """Generate content using Gemini with graceful model fallback."""
    if not settings.gemini_api_key:
        return ""

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)

        candidates = _model_candidates()
        listed = _list_supported_models(genai)

        for name in listed:
            if name not in candidates:
                candidates.append(name)

        last_error: Exception | None = None
        for model_name in candidates:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                response_text = (getattr(response, "text", "") or "").strip()
                if response_text:
                    return response_text
            except Exception as exc:
                last_error = exc
                continue

        if last_error:
            LOGGER.warning("Gemini generation failed across candidate models: %s", last_error)
        return ""
    except Exception as exc:
        LOGGER.warning("Gemini client initialization failed: %s", exc)
        return ""


def _fallback_reply(strategy: str, intent: str, emotion: str, context_docs: List[str]) -> str:
    """Build a short policy-first fallback reply when Gemini is unavailable."""
    context_hint = ""
    if context_docs:
        context_hint = context_docs[0]

    base = (
        "Thanks for your email. We understand your concern and are here to help. "
        "Based on our support policy, we will guide you through the next steps."
    )

    if intent == "Refund Request":
        base = (
            "Thanks for reaching out about your refund request. "
            "We can help review eligibility and next steps under our refund policy."
        )
    elif intent == "Order Status":
        base = (
            "Thanks for checking on your order. "
            "We will verify the latest shipping status and provide an update."
        )

    if emotion in {"angry", "frustrated", "urgent"}:
        base = "We are sorry for the inconvenience. " + base

    if strategy == "policy_focused" and context_hint:
        return f"{base}\n\nRelevant policy context:\n{context_hint}"
    return base


def generate_reply(
    strategy: str,
    intent: str,
    emotion: str,
    context_docs: List[str],
    similar_user_docs: List[str],
    customer_text: str,
) -> str:
    """Generate a policy-grounded reply from strategy, NLP outputs, and retrieved context."""
    context_block = "\n\n".join(context_docs) if context_docs else "No internal policy context found."
    user_history_block = "\n\n".join(similar_user_docs) if similar_user_docs else "No similar past user messages found."

    prompt = (
        "You are a customer support email assistant.\n"
        "Use ONLY the provided policy context for policy claims.\n"
        "Use similar past customer messages only for continuity and tone, not policy facts.\n"
        "If context is insufficient, ask one short follow-up question instead of inventing details.\n"
        "Keep tone professional, empathetic, and concise.\n"
        "Do not mention internal tools, vector DB, or model names.\n\n"
        f"Strategy: {strategy}\n"
        f"Intent: {intent}\n"
        f"Emotion: {emotion}\n"
        f"Customer message: {customer_text}\n\n"
        f"Relevant policy context:\n{context_block}\n\n"
        f"Similar past customer messages:\n{user_history_block}\n\n"
        "Output: A complete email body only."
    )

    generated = _gemini_generate(prompt)
    if generated:
        return generated

    return _fallback_reply(strategy=strategy, intent=intent, emotion=emotion, context_docs=context_docs)
