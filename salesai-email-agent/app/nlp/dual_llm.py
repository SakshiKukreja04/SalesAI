"""Unified dual-LLM interface for memory-aware intent and emotion detection with automatic selection."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.nlp.groq_client import get_intent_and_emotion_groq
from app.nlp.llm_selector import select_best_llm_output
from app.nlp.memory_nlp_classifier import classify_intent_and_emotion_with_memory

LOGGER = logging.getLogger(__name__)


def detect_intent_emotion_gemini(
    text: str,
    customer_memory: Optional[Any] = None,
    kb_context: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Detect both intent and emotion using Gemini API with memory supporting evidence."""
    if not text or not text.strip():
        LOGGER.warning("Gemini dual detection: input text is empty")
        return {
            "intent": "general_support",
            "intent_confidence": 0.5,
            "emotion": "neutral",
            "emotion_confidence": 0.5,
            "reasoning_summary": "Empty customer message.",
            "memory_used": False,
        }

    try:
        result = classify_intent_and_emotion_with_memory(
            message=text,
            customer_memory=customer_memory,
            kb_context=kb_context,
        )

        LOGGER.info(
            "[GEMINI NLP ANALYSIS] intent=%s (conf=%.2f) | emotion=%s (conf=%.2f) | memory_used=%s | reason=%s",
            result.get("intent"),
            result.get("intent_confidence"),
            result.get("emotion"),
            result.get("emotion_confidence"),
            result.get("memory_used"),
            result.get("reasoning_summary"),
        )
        return result

    except Exception as exc:
        LOGGER.error("Gemini dual detection failed: %s", exc)
        return {
            "intent": "general_support",
            "intent_confidence": 0.5,
            "emotion": "neutral",
            "emotion_confidence": 0.5,
            "reasoning_summary": f"Fallback due to error: {exc}",
            "memory_used": False,
        }


def select_best_nlp_output(
    text: str,
    customer_memory: Optional[Any] = None,
    kb_context: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run both Gemini (with memory context) and Groq in parallel and select best result.
    
    Returns dictionary with:
    - intent: str
    - intent_confidence: float
    - emotion: str
    - emotion_confidence: float
    - reasoning_summary: str
    - memory_used: bool
    - selected_model: str ("gemini" | "groq" | "default")
    """
    try:
        gemini_result = None
        groq_result = None
        gemini_error = None
        groq_error = None

        def run_gemini():
            nonlocal gemini_result, gemini_error
            try:
                gemini_result = detect_intent_emotion_gemini(
                    text=text,
                    customer_memory=customer_memory,
                    kb_context=kb_context,
                )
            except Exception as exc:
                gemini_error = exc
                LOGGER.error("Gemini parallel execution failed: %s", exc)

        def run_groq():
            nonlocal groq_result, groq_error
            try:
                groq_result = get_intent_and_emotion_groq(text)
            except Exception as exc:
                groq_error = exc
                LOGGER.error("Groq parallel execution failed: %s", exc)

        import threading

        gemini_thread = threading.Thread(target=run_gemini, daemon=False)
        groq_thread = threading.Thread(target=run_groq, daemon=False)

        gemini_thread.start()
        groq_thread.start()

        gemini_thread.join(timeout=15)
        groq_thread.join(timeout=15)

        # Handle results
        if gemini_result and groq_result:
            final_result = select_best_llm_output(gemini_result, groq_result)
            # Ensure memory fields are preserved from gemini_result if gemini won
            if final_result.get("selected_model") == "gemini" or gemini_result.get("memory_used"):
                final_result["reasoning_summary"] = gemini_result.get("reasoning_summary", "Classified with Gemini.")
                final_result["memory_used"] = gemini_result.get("memory_used", False)
            else:
                final_result["reasoning_summary"] = groq_result.get("reasoning_summary", "Classified with Groq.")
                final_result["memory_used"] = False
            return final_result

        elif gemini_result:
            LOGGER.info(
                "[DUAL-LLM] Using Gemini: intent=%s (%.2f), emotion=%s (%.2f), memory_used=%s",
                gemini_result.get("intent"),
                gemini_result.get("intent_confidence", 0.0),
                gemini_result.get("emotion"),
                gemini_result.get("emotion_confidence", 0.0),
                gemini_result.get("memory_used"),
            )
            gemini_result["selected_model"] = "gemini"
            return gemini_result

        elif groq_result:
            LOGGER.info(
                "[DUAL-LLM] Using Groq fallback: intent=%s (%.2f), emotion=%s (%.2f)",
                groq_result.get("intent"),
                groq_result.get("intent_confidence", 0.0),
                groq_result.get("emotion"),
                groq_result.get("emotion_confidence", 0.0),
            )
            groq_result["selected_model"] = "groq"
            groq_result["reasoning_summary"] = "Classified with Groq."
            groq_result["memory_used"] = False
            return groq_result

        else:
            LOGGER.error("[DUAL-LLM] Both Gemini and Groq failed, using heuristic")
            from app.nlp.memory_nlp_classifier import _heuristic_nlp_disambiguation
            heuristic = _heuristic_nlp_disambiguation(text, customer_memory, kb_context)
            data = heuristic.model_dump()
            data["selected_model"] = "heuristic_fallback"
            return data

    except Exception as exc:
        LOGGER.error("Dual LLM selection failed: %s", exc)
        return {
            "intent": "general_support",
            "intent_confidence": 0.5,
            "emotion": "neutral",
            "emotion_confidence": 0.5,
            "reasoning_summary": f"Fallback error: {exc}",
            "memory_used": False,
            "selected_model": "error",
        }
