"""Emotion detection module.

Uses simple keyword heuristics and a Gemini placeholder function for easy
extension into production-grade sentiment/emotion modeling.
"""

from app.config import settings


def _gemini_emotion_placeholder(text: str) -> str:
    """Placeholder for Gemini emotion detection call."""
    if settings.gemini_api_key:
        # Replace this block with an actual Gemini API request.
        pass

    text_l = text.lower()
    if any(word in text_l for word in ["angry", "upset", "bad", "worst", "frustrated"]):
        return "negative"
    if any(word in text_l for word in ["thanks", "great", "happy", "love"]):
        return "positive"
    return "neutral"


def detect_emotion(text: str) -> str:
    """Detect customer emotion as positive, neutral, or negative."""
    return _gemini_emotion_placeholder(text)
