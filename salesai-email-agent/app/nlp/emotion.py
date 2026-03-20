"""Emotion detection module for SalesAI using Gemini API."""

from __future__ import annotations

import json
import logging
import os
from typing import Dict

from dotenv import load_dotenv


load_dotenv()

LOGGER = logging.getLogger(__name__)

ALLOWED_EMOTIONS = {
    "positive",
    "neutral",
    "frustrated",
    "angry",
    "urgent",
    "confused",
}

FALLBACK_RESULT = {"emotion": "neutral", "confidence": "low"}


def clean_response(text: str) -> str:
    """Extract JSON object from model output safely."""
    if not text:
        return ""

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return ""

    return text[start : end + 1]


def _normalize_confidence(value: str) -> str:
    """Map confidence text to high, medium, or low."""
    confidence = (value or "").strip().lower()
    if confidence in {"high", "medium", "low"}:
        return confidence
    return "low"


def _heuristic_fallback(text: str) -> Dict[str, str]:
    """Keyword fallback used when API or parsing fails."""
    t = text.lower()
    if any(word in t for word in ["urgent", "asap", "immediately", "right now"]):
        return {"emotion": "urgent", "confidence": "medium"}
    if any(word in t for word in ["angry", "furious", "worst", "unacceptable"]):
        return {"emotion": "angry", "confidence": "medium"}
    if any(word in t for word in ["frustrated", "upset", "annoyed", "still waiting"]):
        return {"emotion": "frustrated", "confidence": "medium"}
    if any(word in t for word in ["what", "how", "confused", "not sure", "dont understand"]):
        return {"emotion": "confused", "confidence": "medium"}
    if any(word in t for word in ["thanks", "great", "happy", "love"]):
        return {"emotion": "positive", "confidence": "medium"}
    return FALLBACK_RESULT.copy()


def _parse_model_json(response_text: str) -> Dict[str, str]:
    """Parse model JSON output and enforce allowed values."""
    cleaned = clean_response(response_text)
    if not cleaned:
        return FALLBACK_RESULT.copy()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return FALLBACK_RESULT.copy()

    emotion = str(data.get("emotion", "")).strip().lower()
    confidence = _normalize_confidence(str(data.get("confidence", "")))

    if emotion not in ALLOWED_EMOTIONS:
        return FALLBACK_RESULT.copy()

    return {"emotion": emotion, "confidence": confidence}


def _model_candidates_from_env() -> list[str]:
    """Build ordered candidate model names from env and sane defaults."""
    configured = os.getenv("GEMINI_MODEL", "").strip()
    candidates = [
        configured,
        "gemini-2.0-flash",
        "models/gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "models/gemini-2.0-flash-lite",
        "gemini-2.0-pro",
        "models/gemini-2.0-pro",
        "gemini-1.5-flash",
        "models/gemini-1.5-flash",
        "gemini-1.5-pro",
        "models/gemini-1.5-pro",
        "gemini-pro",
        "models/gemini-pro",
    ]
    return [name for name in candidates if name]


def _list_supported_models(genai_module: object) -> list[str]:
    """Return model names that support generateContent, if listing succeeds."""
    try:
        supported: list[str] = []
        for model in genai_module.list_models():
            methods = getattr(model, "supported_generation_methods", []) or []
            if "generateContent" in methods:
                name = getattr(model, "name", "")
                if name:
                    supported.append(name.replace("models/", ""))
        return supported
    except Exception:
        return []


def _generate_with_retry(genai_module: object, prompt: str) -> str:
    """Try prompt generation across candidate Gemini models."""
    candidates = _model_candidates_from_env()
    listed = _list_supported_models(genai_module)

    for name in listed:
        if name not in candidates:
            candidates.append(name)

    last_error: Exception | None = None

    for model_name in candidates:
        try:
            model = genai_module.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            response_text = getattr(response, "text", "") or ""
            if response_text.strip():
                return response_text
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error

    return ""


def detect_emotion(text: str) -> Dict[str, str]:
    """Detect emotional tone into one label with confidence."""
    if not text or not text.strip():
        LOGGER.info("Emotion input text is empty. Falling back to neutral.")
        return FALLBACK_RESULT.copy()

    api_key = os.getenv("GEMINI_API_KEY", "")

    if not api_key:
        result = _heuristic_fallback(text)
        LOGGER.info("Emotion input=%r | emotion=%s | confidence=%s", text, result["emotion"], result["confidence"])
        return result

    prompt = (
        "You are an AI assistant for customer sentiment analysis.\n\n"
        "Classify the emotional tone of the following customer message into ONE of:\n"
        "positive, neutral, frustrated, angry, urgent, confused.\n\n"
        "Also estimate confidence as High, Medium, or Low.\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        "    \"emotion\": \"...\",\n"
        "    \"confidence\": \"...\"\n"
        "}\n\n"
        f"Customer message:\n{text}"
    )

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)

        response_text = _generate_with_retry(genai, prompt)

        result = _parse_model_json(response_text)
        if result == FALLBACK_RESULT:
            result = _heuristic_fallback(text)

        LOGGER.info("Emotion input=%r | emotion=%s | confidence=%s", text, result["emotion"], result["confidence"])
        return result

    except Exception as exc:
        LOGGER.warning("Gemini emotion detection failed, using fallback: %s", exc)
        result = _heuristic_fallback(text)
        LOGGER.info("Emotion input=%r | emotion=%s | confidence=%s", text, result["emotion"], result["confidence"])
        return result


def detect_emotion_for_email(email_id: str, text: str) -> Dict[str, str]:
    """Detect emotion for an email and log email ID with detected emotion."""
    result = detect_emotion(text)
    LOGGER.info("email_id=%s | emotion=%s | confidence=%s", email_id, result["emotion"], result["confidence"])
    return result
