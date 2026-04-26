"""Intent classification module for SalesAI using Gemini API."""

from __future__ import annotations

import json
import logging
import os
import re
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

FALLBACK_RESULT = {"intent": "Inquiry", "confidence": "low"}


def _model_candidates_from_env() -> list[str]:
    """Build ordered candidate model names from env and sane defaults."""
    configured = os.getenv("GEMINI_MODEL", "").strip()
    candidates = [
        configured,
        "gemini-2.0-flash",
        "models/gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "models/gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "models/gemini-1.5-flash",
        "gemini-1.5-flash-latest",
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

    # Prefer user/env candidates first, then any API-listed supported models.
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
    if any(word in t for word in ["refund", "return", "money back"]):
        return {"intent": "Refund Request", "confidence": "medium"}
    if any(word in t for word in ["where is my order", "track", "shipping", "delivered", "not received"]):
        return {"intent": "Order Status", "confidence": "medium"}
    if any(word in t for word in ["broken", "bad", "worst", "angry", "complaint"]):
        return {"intent": "Complaint", "confidence": "medium"}
    if any(word in t for word in ["price", "size", "color", "material", "feature"]):
        return {"intent": "Product Question", "confidence": "medium"}
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

    intent = str(data.get("intent", "")).strip()
    confidence = _normalize_confidence(str(data.get("confidence", "")))

    if intent not in ALLOWED_INTENTS:
        return FALLBACK_RESULT.copy()

    return {"intent": intent, "confidence": confidence}


def classify_intent(text: str) -> Dict[str, str]:
    """Classify a customer message into one business intent with confidence."""
    if not text or not text.strip():
        LOGGER.info("Intent input text is empty. Falling back to default intent.")
        return FALLBACK_RESULT.copy()

    api_key = os.getenv("GEMINI_API_KEY", "")

    if not api_key:
        result = _heuristic_fallback(text)
        LOGGER.info("Intent input=%r | intent=%s | confidence=%s", text, result["intent"], result["confidence"])
        return result

    prompt = (
        "You are an AI assistant for an e-commerce company.\n\n"
        "Classify the following customer message into ONE intent only from:\n"
        "Complaint, Inquiry, Refund Request, Order Status, Product Question.\n\n"
        "Also estimate confidence as High, Medium, or Low.\n\n"
        "Return output ONLY in this JSON format:\n"
        "{\n"
        "    \"intent\": \"...\",\n"
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

        LOGGER.info("Intent input=%r | intent=%s | confidence=%s", text, result["intent"], result["confidence"])
        return result

    except Exception as exc:
        LOGGER.warning("Gemini intent classification failed, using fallback: %s", exc)
        result = _heuristic_fallback(text)
        LOGGER.info("Intent input=%r | intent=%s | confidence=%s", text, result["intent"], result["confidence"])
        return result


def classify_intent_for_email(email_id: str, text: str) -> Dict[str, str]:
    """Classify intent for an email and log email ID with detected intent."""
    result = classify_intent(text)
    LOGGER.info("email_id=%s | intent=%s | confidence=%s", email_id, result["intent"], result["confidence"])
    return result


def _confidence_to_float(confidence_str: str) -> float:
    """Convert confidence string (high/medium/low) to float (0.0-1.0)."""
    confidence = (confidence_str or "").strip().lower()
    if confidence == "high":
        return 0.9
    elif confidence == "medium":
        return 0.7
    else:
        return 0.5


def detect_intent_emotion_gemini(text: str) -> Dict[str, float | str]:
    """Classify intent using Gemini with standardized float confidence output.
    
    Returns:
        Dictionary with keys:
        - intent: str
        - intent_confidence: float (0.0-1.0)
    """
    if not text or not text.strip():
        LOGGER.info("Intent input text is empty, returning fallback")
        return {
            "intent": "Inquiry",
            "intent_confidence": 0.5,
        }

    api_key = os.getenv("GEMINI_API_KEY", "")

    if not api_key:
        result = _heuristic_fallback(text)
        confidence = _confidence_to_float(result["confidence"])
        LOGGER.info(
            "Gemini intent: input=%r | intent=%s (%.2f)",
            text,
            result["intent"],
            confidence,
        )
        return {
            "intent": result["intent"],
            "intent_confidence": confidence,
        }

    prompt = (
        "You are an AI assistant for an e-commerce company.\n\n"
        "Classify the following customer message into ONE intent only from:\n"
        "Complaint, Inquiry, Refund Request, Order Status, Product Question.\n\n"
        "Also estimate confidence as High, Medium, or Low.\n\n"
        "Return output ONLY in this JSON format:\n"
        "{\n"
        "    \"intent\": \"...\",\n"
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

        confidence = _confidence_to_float(result["confidence"])
        LOGGER.info(
            "Gemini intent: intent=%s (%.2f)",
            result["intent"],
            confidence,
        )
        return {
            "intent": result["intent"],
            "intent_confidence": confidence,
        }

    except Exception as exc:
        LOGGER.warning("Gemini intent classification failed: %s", exc)
        result = _heuristic_fallback(text)
        confidence = _confidence_to_float(result["confidence"])
        return {
            "intent": result["intent"],
            "intent_confidence": confidence,
        }
