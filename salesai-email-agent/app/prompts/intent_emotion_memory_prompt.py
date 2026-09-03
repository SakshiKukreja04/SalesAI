"""Prompt builder for memory-aware intent and emotion detection (SalesAI V3)."""

from __future__ import annotations

from typing import Any, List, Optional
from app.prompts.emotion_prompt import EMOTION_TAXONOMY
from app.prompts.intent_prompt import INTENT_TAXONOMY


def build_memory_aware_nlp_prompt(
    current_message: str,
    customer_memory_summary: str = "",
    recent_interactions: str = "",
    open_issues: str = "",
    kb_context: str = "",
    intent_taxonomy: Optional[List[str]] = None,
    emotion_taxonomy: Optional[List[str]] = None,
) -> str:
    """Build the prompt for memory-aware intent and emotion classification."""
    intents = intent_taxonomy or INTENT_TAXONOMY
    emotions = emotion_taxonomy or EMOTION_TAXONOMY

    memory_summary_block = (
        f"CUSTOMER MEMORY SUMMARY:\n{customer_memory_summary.strip()}\n\n"
        if customer_memory_summary and customer_memory_summary.strip()
        else ""
    )

    open_issues_block = (
        f"OPEN ISSUES:\n{open_issues.strip()}\n\n"
        if open_issues and open_issues.strip()
        else ""
    )

    recent_interactions_block = (
        f"RECENT INTERACTIONS:\n{recent_interactions.strip()}\n\n"
        if recent_interactions and recent_interactions.strip()
        else ""
    )

    kb_block = (
        f"CURRENT SHOPIFYX KB CONTEXT:\n{kb_context.strip()}\n\n"
        if kb_context and kb_context.strip()
        else ""
    )

    return (
        "You are the Intent and Emotion Classification module of ShopiFyX SalesAI.\n\n"
        "Your task is to classify the customer's PRIMARY intent and dominant emotion.\n\n"
        "ALLOWED INTENTS:\n"
        + "- " + "\n- ".join(intents) + "\n\n"
        "ALLOWED EMOTIONS:\n"
        + "- " + "\n- ".join(emotions) + "\n\n"
        "CORE RULES:\n"
        "1. CURRENT MESSAGE PRIORITY:\n"
        "   - The current message always has the highest priority.\n"
        "   - Never let customer memory override a clear, unambiguous statement in the current message.\n"
        "2. PRE-PURCHASE vs. POST-PURCHASE DISAMBIGUATION:\n"
        "   - If the customer mentions an item that was already purchased/shipped/in transit (e.g. 'I ordered shoes... delivery partner contacted me...'), DO NOT classify as product_inquiry or product_details.\n"
        "   - Classify missed delivery, partner contact, away on travel, or schedule conflict as 'delayed_delivery' or 'delivery_issue'.\n"
        "   - Only classify as 'product_inquiry' / 'product_details' / 'product_recommendation' if the user is researching/buying new items.\n"
        "3. CONTEXTUAL EVIDENCE & AMBIGUITY RESOLUTION:\n"
        "   - Use memory only as supporting contextual evidence when the current message is short,\n"
        "     referential, pronoun-heavy ('it', 'that', 'the same one'), or a conversation continuation.\n"
        "   - Examples:\n"
        "     * 'Still waiting for it.' -> Use previous interactions/open issues to identify what 'it' refers to (e.g., refund vs. delivery).\n"
        "     * 'Same issue again.' -> Inspect open issues and recent interactions.\n"
        "     * 'Can I get the same one?' -> Inspect recently discussed products in memory.\n"
        "     * 'Thanks, that worked.' -> Previous interaction helps identify what was resolved.\n"
        "4. EMOTION DETECTION RULES:\n"
        "   - Emotion detection must primarily analyze the current message.\n"
        "   - Do NOT mark polite openings ('Thank you for your response...') as satisfied if the customer proceeds to describe a problem, confusion, or missed delivery ('What can I do now?'). Classify actual tone (confused, worried, neutral, frustrated).\n"
        "5. DO NOT EXPOSE CHAIN-OF-THOUGHT:\n"
        "   - Provide a concise 1-sentence 'reasoning_summary' suitable for system logs and debugging.\n"
        "   - Set 'memory_used' to true if historical memory/issues helped disambiguate the intent/emotion, else false.\n\n"
        + memory_summary_block
        + open_issues_block
        + recent_interactions_block
        + kb_block
        + "CURRENT MESSAGE:\n"
        + current_message.strip() + "\n\n"
        "Return ONLY valid JSON matching this schema:\n"
        "{\n"
        '  "intent": "<one_allowed_intent>",\n'
        '  "intent_confidence": 0.0,\n'
        '  "emotion": "<one_allowed_emotion>",\n'
        '  "emotion_confidence": 0.0,\n'
        '  "reasoning_summary": "<short reason>",\n'
        '  "memory_used": false\n'
        "}"
    )
