"""Unified dual-LLM interface for intent and emotion detection with automatic selection."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict

from app.nlp.groq_client import get_intent_and_emotion_groq
from app.nlp.llm_selector import select_best_llm_output


LOGGER = logging.getLogger(__name__)


def detect_intent_emotion_gemini(text: str) -> Dict[str, float | str]:
    """Detect both intent and emotion using Gemini API.
    
    Args:
        text: Customer message text
    
    Returns:
        Dictionary with keys:
        - intent: str
        - intent_confidence: float (0.0-1.0)
        - emotion: str
        - emotion_confidence: float (0.0-1.0)
    """
    from app.nlp.intent import detect_intent_emotion_gemini as gemini_intent
    from app.nlp.emotion import detect_intent_emotion_gemini as gemini_emotion
    
    if not text or not text.strip():
        LOGGER.warning("Gemini dual detection: input text is empty")
        return {
            "intent": "Inquiry",
            "intent_confidence": 0.5,
            "emotion": "neutral",
            "emotion_confidence": 0.5,
        }
    
    try:
        # Get intent result
        intent_result = gemini_intent(text)
        intent = intent_result.get("intent", "Inquiry")
        intent_conf = float(intent_result.get("intent_confidence", 0.5))
        
        # Get emotion result
        emotion_result = gemini_emotion(text)
        emotion = emotion_result.get("emotion", "neutral")
        emotion_conf = float(emotion_result.get("emotion_confidence", 0.5))
        
        result = {
            "intent": intent,
            "intent_confidence": intent_conf,
            "emotion": emotion,
            "emotion_confidence": emotion_conf,
        }
        
        LOGGER.info(
            "[GEMINI ANALYSIS] "
            "intent=%s (confidence=%.2f) | emotion=%s (confidence=%.2f)",
            intent,
            intent_conf,
            emotion,
            emotion_conf,
        )
        
        return result
    
    except Exception as exc:
        LOGGER.error("Gemini dual detection failed: %s", exc)
        return {
            "intent": "Inquiry",
            "intent_confidence": 0.5,
            "emotion": "neutral",
            "emotion_confidence": 0.5,
        }


def select_best_nlp_output(text: str) -> Dict[str, float | str]:
    """Run both Gemini and Groq in parallel and select best result using confidence scoring.
    
    This function:
    1. Calls both Gemini and Groq APIs in parallel
    2. Compares their confidence scores
    3. Selects the result with highest combined score
    4. Falls back gracefully if one LLM fails
    
    Args:
        text: Customer message text
    
    Returns:
        Dictionary with keys:
        - intent: str
        - intent_confidence: float (0.0-1.0)
        - emotion: str
        - emotion_confidence: float (0.0-1.0)
        - selected_model: "gemini" or "groq"
        - gemini_score: float
        - groq_score: float
    """
    try:
        # Try to run both APIs in parallel using threading
        gemini_result = None
        groq_result = None
        gemini_error = None
        groq_error = None
        
        def run_gemini():
            nonlocal gemini_result, gemini_error
            try:
                gemini_result = detect_intent_emotion_gemini(text)
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
        
        # Use threading for parallel execution
        import threading
        
        gemini_thread = threading.Thread(target=run_gemini, daemon=False)
        groq_thread = threading.Thread(target=run_groq, daemon=False)
        
        gemini_thread.start()
        groq_thread.start()
        
        # Wait for both to complete (with timeout)
        gemini_thread.join(timeout=15)  # 15 second timeout per thread
        groq_thread.join(timeout=15)
        
        # Handle results with fallback logic
        if gemini_result and groq_result:
            # Both succeeded - use selector
            final_result = select_best_llm_output(gemini_result, groq_result)
            return final_result
        
        elif gemini_result:
            # Groq failed - use Gemini
            LOGGER.warning(
                "[DUAL-LLM FALLBACK] Groq failed, using Gemini: "
                "intent=%s (%.2f), emotion=%s (%.2f)",
                gemini_result.get("intent", "?"),
                gemini_result.get("intent_confidence", 0.0),
                gemini_result.get("emotion", "?"),
                gemini_result.get("emotion_confidence", 0.0),
            )
            gemini_result["selected_model"] = "gemini"
            gemini_result["gemini_score"] = 0.0
            gemini_result["groq_score"] = 0.0
            return gemini_result
        
        elif groq_result:
            # Gemini failed - use Groq
            LOGGER.warning(
                "[DUAL-LLM FALLBACK] Gemini failed, using Groq: "
                "intent=%s (%.2f), emotion=%s (%.2f)",
                groq_result.get("intent", "?"),
                groq_result.get("intent_confidence", 0.0),
                groq_result.get("emotion", "?"),
                groq_result.get("emotion_confidence", 0.0),
            )
            groq_result["selected_model"] = "groq"
            groq_result["gemini_score"] = 0.0
            groq_result["groq_score"] = 0.0
            return groq_result
        
        else:
            # Both failed - return default
            LOGGER.error("[DUAL-LLM FALLBACK] Both Gemini and Groq failed, returning default")
            return {
                "intent": "Inquiry",
                "intent_confidence": 0.5,
                "emotion": "neutral",
                "emotion_confidence": 0.5,
                "selected_model": "default",
                "gemini_score": 0.0,
                "groq_score": 0.0,
            }
    
    except Exception as exc:
        LOGGER.error("Dual LLM selection failed: %s", exc)
        return {
            "intent": "Inquiry",
            "intent_confidence": 0.5,
            "emotion": "neutral",
            "emotion_confidence": 0.5,
            "selected_model": "error",
            "gemini_score": 0.0,
            "groq_score": 0.0,
        }
