"""Response generation module.

Builds customer-facing replies using selected strategy and retrieved knowledge.
A Gemini generator is used when configured, with deterministic fallback output.
"""

import logging
import re
from typing import List

from app.config import settings


LOGGER = logging.getLogger(__name__)


def _strategy_tone_guidance(strategy: str, emotion: str) -> str:
    """Return concise tone instructions aligned with selected strategy."""
    tone = "Use a professional, warm, and clear tone."
    if strategy == "empathetic" or emotion in {"angry", "frustrated", "urgent"}:
        tone = "Use an empathetic, calm, and reassuring tone."
    elif strategy == "policy_focused":
        tone = "Use a policy-accurate and reassuring tone with clear next steps."
    elif strategy == "tracking_focused":
        tone = "Use a proactive status-update tone and set clear expectations."
    return tone


def _email_style_instructions(strategy: str, intent: str, emotion: str) -> str:
    """Build formatting guidance so replies read like human customer support emails."""
    return (
        f"Strategy: {strategy}\n"
        f"Intent: {intent}\n"
        f"Emotion: {emotion}\n"
        f"Tone guidance: {_strategy_tone_guidance(strategy, emotion)}\n"
        "Write in 2-3 short paragraphs using complete sentences.\n"
        "Acknowledge the customer concern in the opening sentence.\n"
        "Answer the question directly and clearly, without sounding robotic.\n"
        "Avoid bullet points unless the customer explicitly asks for a list.\n"
        "Do not include internal notes, model references, or policy speculation.\n"
        "Do not include an email signature or sign-off name."
    )


def _extract_timeline_facts(context_docs: List[str]) -> List[str]:
    """Extract timeline snippets from context to improve fallback readability."""
    joined = "\n".join(context_docs)
    if not joined.strip():
        return []
    patterns = [
        r"pickup\s+within\s+\d+\s*(?:-|to)\s*\d+\s+days",
        r"refund\s+processed\s+within\s+\d+\s*(?:-|to)\s*\d+\s+business\s+days",
        r"credited\s+to\s+original\s+payment\s+method",
    ]
    facts: List[str] = []
    for pattern in patterns:
        match = re.search(pattern, joined, flags=re.IGNORECASE)
        if match:
            facts.append(match.group(0).strip())
    return facts


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

    base = "I'm not sure, let me connect you to support."

    if intent == "Refund Request" and context_docs:
        timeline_facts = _extract_timeline_facts(context_docs)
        if timeline_facts:
            pickup = next((f for f in timeline_facts if f.lower().startswith("pickup")), "")
            refund = next((f for f in timeline_facts if f.lower().startswith("refund")), "")
            credit = next((f for f in timeline_facts if "credited" in f.lower()), "")
            details = ". ".join([fact for fact in [pickup.capitalize(), refund.capitalize(), credit.capitalize()] if fact])
            base = (
                "Thanks for reaching out about your refund request. "
                + details
                + "."
            ).replace("..", ".")
        else:
            base = "Thanks for reaching out about your refund request."
    elif intent == "Order Status" and context_docs:
        base = "Thanks for checking on your order status. We will keep you updated with the latest tracking progress."

    if emotion in {"angry", "frustrated", "urgent"} and context_docs:
        base = "We are sorry for the inconvenience. " + base

    if strategy == "policy_focused" and context_hint and "I'm not sure" not in base:
        return base
    return base


def _format_reply_sections(reply_text: str, intent: str) -> str:
    """Format reply with proper text justification and spacing."""
    if not reply_text.strip():
        return reply_text
    
    # Split into logical paragraphs and add spacing
    lines = reply_text.strip().split("\n")
    formatted_lines = []
    
    for line in lines:
        stripped = line.strip()
        if stripped:
            formatted_lines.append(stripped)
    
    # Join with double newlines for better spacing
    spaced = "\n\n".join(formatted_lines)
    
    # Clean up any excessive spacing
    while "\n\n\n" in spaced:
        spaced = spaced.replace("\n\n\n", "\n\n")
    
    return spaced


def generate_reply(
    strategy: str,
    intent: str,
    emotion: str,
    context_docs: List[str],
    similar_user_docs: List[str],
    customer_text: str,
    strict_prompt: str | None = None,
) -> str:
    """Generate a policy-grounded reply from strategy, NLP outputs, and retrieved context."""
    style_block = _email_style_instructions(strategy=strategy, intent=intent, emotion=emotion)
    if strict_prompt:
        prompt = (
            f"{strict_prompt}\n\n"
            "Reply requirements:\n"
            f"{style_block}\n"
            "Format reply with clear sections and line breaks for readability.\n"
        )
    else:
        context_block = "\n\n".join(context_docs) if context_docs else "No internal policy context found."
        user_history_block = "\n\n".join(similar_user_docs) if similar_user_docs else "No similar past user messages found."

        prompt = (
            "You are a customer support email assistant.\n"
            "Use ONLY the provided policy context for policy claims.\n"
            "Use similar past customer messages only for continuity and tone, not policy facts.\n"
            "If context is insufficient, ask one short follow-up question instead of inventing details.\n"
            "Keep tone professional, empathetic, and concise.\n"
            "Do not mention internal tools, vector DB, or model names.\n"
            "Format reply with clear sections and line breaks between topics for readability.\n\n"
            f"{style_block}\n\n"
            f"Customer message: {customer_text}\n\n"
            f"Relevant policy context:\n{context_block}\n\n"
            f"Similar past customer messages:\n{user_history_block}\n\n"
            "Output: A complete email body only. Use line breaks to separate sections."
        )

    generated = _gemini_generate(prompt)
    if generated:
        formatted = _format_reply_sections(generated, intent)
        return formatted

    fallback = _fallback_reply(strategy=strategy, intent=intent, emotion=emotion, context_docs=context_docs)
    return _format_reply_sections(fallback, intent)
