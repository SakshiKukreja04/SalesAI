"""Groq API client for intent classification and emotion detection."""

from __future__ import annotations

import json
import logging
import os
from typing import Dict

from dotenv import load_dotenv


load_dotenv()

LOGGER = logging.getLogger(__name__)

ALLOWED_INTENTS = {
    "Complaint",
    "Inquiry",
    "Refund Request",
    "Order Status",
    "Product Question",
}

ALLOWED_EMOTIONS = {
    "positive",
    "neutral",
    "frustrated",
    "angry",
    "urgent",
    "confused",
}


def _confidence_string_to_float(confidence_str: str) -> float:
    """Convert confidence string (high/medium/low) to float (0.0-1.0)."""
    confidence = (confidence_str or "").strip().lower()
    if confidence == "high":
        return 0.9
    elif confidence == "medium":
        return 0.7
    else:
        return 0.5


def _clean_response(text: str) -> str:
    """Extract JSON object from model output safely."""
    if not text:
        return ""

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return ""

    return text[start : end + 1]


def _parse_json_response(response_text: str, response_type: str) -> Dict[str, float] | None:
    """Parse model JSON output and enforce allowed values.
    
    Args:
        response_text: Raw model response
        response_type: Either "intent" or "emotion"
    
    Returns:
        Dict with keys like "intent"/"emotion" and "confidence" (float 0.0-1.0),
        or None if parsing fails.
    """
    cleaned = _clean_response(response_text)
    if not cleaned:
        return None

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if response_type == "intent":
        intent = str(data.get("intent", "")).strip()
        confidence_str = str(data.get("confidence", "medium"))
        
        if intent not in ALLOWED_INTENTS:
            return None
        
        confidence = _confidence_string_to_float(confidence_str)
        return {
            "intent": intent,
            "intent_confidence": confidence,
        }
    
    elif response_type == "emotion":
        emotion = str(data.get("emotion", "")).strip().lower()
        confidence_str = str(data.get("confidence", "medium"))
        
        if emotion not in ALLOWED_EMOTIONS:
            return None
        
        confidence = _confidence_string_to_float(confidence_str)
        return {
            "emotion": emotion,
            "emotion_confidence": confidence,
        }
    
    return None


def get_intent_and_emotion_groq(text: str) -> Dict[str, float | str]:
    """Detect both intent and emotion using Groq API with deterministic prompting.
    
    Args:
        text: Customer message text
    
    Returns:
        Dictionary with keys:
        - intent: str
        - intent_confidence: float (0.0-1.0)
        - emotion: str
        - emotion_confidence: float (0.0-1.0)
        
        Returns fallback on error with neutral/inquiry defaults.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    
    if not api_key:
        LOGGER.warning("GROQ_API_KEY not configured, returning fallback")
        return {
            "intent": "Inquiry",
            "intent_confidence": 0.5,
            "emotion": "neutral",
            "emotion_confidence": 0.5,
        }
    
    if not text or not text.strip():
        LOGGER.warning("Groq input text is empty, returning fallback")
        return {
            "intent": "Inquiry",
            "intent_confidence": 0.5,
            "emotion": "neutral",
            "emotion_confidence": 0.5,
        }
    
    try:
        from groq import Groq
        
        client = Groq(api_key=api_key)
        
        # Combined prompt for both intent and emotion
        prompt = (
            "You are an AI assistant for customer support intent and emotion analysis.\n\n"
            "STRICT CLASSIFICATION RULES:\n"
            "1. INTENT - Choose ONE from EXACTLY these categories:\n"
            "   - Complaint: Customer reports problem, broken item, poor service\n"
            "   - Refund Request: Customer asks for money back or return\n"
            "   - Order Status: Customer asks about delivery, tracking, where is order\n"
            "   - Product Question: Customer asks about features, specifications, compatibility\n"
            "   - Inquiry: General question about company, policies, or other topics\n\n"
            "2. EMOTION - Choose ONE from EXACTLY these:\n"
            "   - angry: Uses words like 'furious', 'unacceptable', 'worst'\n"
            "   - frustrated: Uses words like 'annoyed', 'upset', 'still waiting'\n"
            "   - urgent: Uses words like 'urgent', 'asap', 'immediately'\n"
            "   - confused: Uses words like 'don't understand', 'how', 'why'\n"
            "   - positive: Uses words like 'thanks', 'great', 'happy'\n"
            "   - neutral: No emotional language, factual tone\n\n"
            "3. CONFIDENCE LEVELS:\n"
            "   - High: Category is very clear, multiple keywords match, high certainty\n"
            "   - Medium: Category is reasonably clear, some keywords match\n"
            "   - Low: Category is unclear, ambiguous, or multiple categories possible\n\n"
            "EXAMPLES:\n"
            "- 'Where is my order?' → intent=Order Status (High), emotion=neutral (High)\n"
            "- 'I want a refund!' → intent=Refund Request (High), emotion=angry (Medium)\n"
            "- 'How do I reset my password?' → intent=Inquiry (High), emotion=neutral (High)\n"
            "- 'Your product is broken!' → intent=Complaint (High), emotion=frustrated (Medium)\n\n"
            "Return ONLY valid JSON, no other text:\n"
            "{\n"
            "    \"intent\": \"<EXACT category name>\",\n"
            "    \"intent_confidence\": \"<High|Medium|Low>\",\n"
            "    \"emotion\": \"<EXACT emotion name>\",\n"
            "    \"emotion_confidence\": \"<High|Medium|Low>\"\n"
            "}\n\n"
            f"Customer message:\n{text}"
        )
        
        # Use temperature=0 for deterministic output
        # Groq uses OpenAI-like chat.completions API
        message = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Current available Groq model
            max_tokens=256,
            temperature=0,  # Deterministic
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
        
        response_text = message.choices[0].message.content if message.choices else ""
        
        if not response_text.strip():
            LOGGER.warning("Groq returned empty response")
            return {
                "intent": "Inquiry",
                "intent_confidence": 0.5,
                "emotion": "neutral",
                "emotion_confidence": 0.5,
            }
        
        # Parse the combined response
        cleaned = _clean_response(response_text)
        if not cleaned:
            LOGGER.warning("Groq response did not contain valid JSON")
            return {
                "intent": "Inquiry",
                "intent_confidence": 0.5,
                "emotion": "neutral",
                "emotion_confidence": 0.5,
            }
        
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            LOGGER.warning("Groq JSON parsing failed: %s", cleaned)
            return {
                "intent": "Inquiry",
                "intent_confidence": 0.5,
                "emotion": "neutral",
                "emotion_confidence": 0.5,
            }
        
        # Extract and validate intent
        intent = str(data.get("intent", "Inquiry")).strip()
        intent_conf_str = str(data.get("intent_confidence", "medium")).strip()
        
        if intent not in ALLOWED_INTENTS:
            intent = "Inquiry"
        intent_confidence = _confidence_string_to_float(intent_conf_str)
        
        # Extract and validate emotion
        emotion = str(data.get("emotion", "neutral")).strip().lower()
        emotion_conf_str = str(data.get("emotion_confidence", "medium")).strip()
        
        if emotion not in ALLOWED_EMOTIONS:
            emotion = "neutral"
        emotion_confidence = _confidence_string_to_float(emotion_conf_str)
        
        LOGGER.info(
            "[GROQ ANALYSIS] "
            "intent=%s (confidence=%.2f) | emotion=%s (confidence=%.2f)",
            intent,
            intent_confidence,
            emotion,
            emotion_confidence,
        )
        
        return {
            "intent": intent,
            "intent_confidence": intent_confidence,
            "emotion": emotion,
            "emotion_confidence": emotion_confidence,
        }
    
    except ImportError:
        LOGGER.error("Groq library not installed. Install with: pip install groq")
        return {
            "intent": "Inquiry",
            "intent_confidence": 0.5,
            "emotion": "neutral",
            "emotion_confidence": 0.5,
        }
    
    except Exception as exc:
        LOGGER.error("Groq API error: %s", exc)
        return {
            "intent": "Inquiry",
            "intent_confidence": 0.5,
            "emotion": "neutral",
            "emotion_confidence": 0.5,
        }
