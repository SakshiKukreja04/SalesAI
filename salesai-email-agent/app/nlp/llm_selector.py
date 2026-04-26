"""Module for selecting the best LLM output between Gemini and Groq."""

from __future__ import annotations

import logging
from typing import Dict, Literal


LOGGER = logging.getLogger(__name__)


def select_best_llm_output(
    gemini_result: Dict[str, float | str],
    groq_result: Dict[str, float | str],
) -> Dict[str, float | str]:
    """Compare Gemini and Groq outputs and select the one with highest confidence.
    
    Scoring formula:
        score = (intent_confidence * 0.6) + (emotion_confidence * 0.4)
    
    Args:
        gemini_result: Result from Gemini with keys:
            - intent: str
            - intent_confidence: float (0.0-1.0)
            - emotion: str
            - emotion_confidence: float (0.0-1.0)
        
        groq_result: Result from Groq with same structure
    
    Returns:
        Dictionary with same keys plus:
        - selected_model: "gemini" or "groq"
        - gemini_score: float (calculated score)
        - groq_score: float (calculated score)
    """
    try:
        # Calculate combined scores
        gemini_intent_conf = float(gemini_result.get("intent_confidence", 0.5))
        gemini_emotion_conf = float(gemini_result.get("emotion_confidence", 0.5))
        gemini_score = (gemini_intent_conf * 0.6) + (gemini_emotion_conf * 0.4)
        
        groq_intent_conf = float(groq_result.get("intent_confidence", 0.5))
        groq_emotion_conf = float(groq_result.get("emotion_confidence", 0.5))
        groq_score = (groq_intent_conf * 0.6) + (groq_emotion_conf * 0.4)
        
        # Log comparison
        LOGGER.info(
            "[LLM COMPARISON] "
            "Gemini → intent=%s (%.2f), emotion=%s (%.2f), score=%.2f | "
            "Groq → intent=%s (%.2f), emotion=%s (%.2f), score=%.2f",
            gemini_result.get("intent", "unknown"),
            gemini_intent_conf,
            gemini_result.get("emotion", "unknown"),
            gemini_emotion_conf,
            gemini_score,
            groq_result.get("intent", "unknown"),
            groq_intent_conf,
            groq_result.get("emotion", "unknown"),
            groq_emotion_conf,
            groq_score,
        )
        
        # Select model with higher score
        if gemini_score >= groq_score:
            selected_model = "gemini"
            selected_result = gemini_result.copy()
        else:
            selected_model = "groq"
            selected_result = groq_result.copy()
        
        # Add metadata
        selected_result["selected_model"] = selected_model
        selected_result["gemini_score"] = gemini_score
        selected_result["groq_score"] = groq_score
        
        LOGGER.info(
            "[LLM SELECTED] Model=%s (score=%.2f vs %.2f)",
            selected_model,
            gemini_score if selected_model == "gemini" else groq_score,
            groq_score if selected_model == "gemini" else gemini_score,
        )
        
        return selected_result
    
    except Exception as exc:
        LOGGER.error("Error during LLM selection: %s", exc)
        # Default to Gemini if comparison fails
        result = gemini_result.copy()
        result["selected_model"] = "gemini"
        result["gemini_score"] = 0.0
        result["groq_score"] = 0.0
        return result
