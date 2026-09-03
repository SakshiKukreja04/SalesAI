"""Emotion detection module for SalesAI using Gemini API.

This version follows the V3 emotion taxonomy: neutral, happy, satisfied,
confused, worried, frustrated, disappointed, angry, urgent.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv

from app.prompts.emotion_prompt import build_emotion_classifier_prompt


load_dotenv()

LOGGER = logging.getLogger(__name__)

EMOTION_TAXONOMY = [
    "neutral",
    "happy",
    "satisfied",
    "confused",
    "worried",
    "frustrated",
    "disappointed",
    "angry",
    "urgent",
]

ALLOWED_EMOTIONS = set(EMOTION_TAXONOMY)
FALLBACK_RESULT = {"emotion": "neutral", "intensity": 0.35, "confidence": 0.45, "signals": ["Insufficient emotional evidence."]}


def clean_response(text: str) -> str:
    if not text:
        return ""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + 1]


def _normalize_confidence(value: Any) -> float:
    try:
        parsed = float(value)
        if 0.0 <= parsed <= 1.0:
            return parsed
    except Exception:
        pass
    lower = str(value).strip().lower()
    if lower in {"high", "very_high"}:
        return 0.9
    if lower in {"medium", "moderate"}:
        return 0.7
    if lower in {"low", "weak"}:
        return 0.45
    return 0.45


def _normalize_intensity(value: Any) -> float:
    try:
        parsed = float(value)
        if 0.0 <= parsed <= 1.0:
            return parsed
    except Exception:
        pass
    return 0.5


from app.nlp.preprocess import strip_email_history


def _model_candidates_from_env() -> list[str]:
    configured = os.getenv("GEMINI_MODEL", "").strip()
    candidates = [
        configured,
        "gemini-3.6-flash",
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "models/gemini-3.6-flash",
        "models/gemini-2.5-flash",
        "models/gemini-1.5-flash",
    ]
    return [name for name in candidates if name]


def _generate_emotion_gemini(api_key: str, prompt: str) -> str:
    candidates = _model_candidates_from_env()
    # 1. Try modern google.genai Client
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        for model_name in candidates:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = (getattr(response, "text", "") or "").strip()
                if text:
                    return text
            except Exception as exc:
                LOGGER.debug("google.genai candidate %s failed: %s", model_name, exc)
                continue
    except ImportError:
        pass

    # 2. Try legacy google.generativeai
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        for model_name in candidates:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                response_text = getattr(response, "text", "") or ""
                if response_text.strip():
                    return response_text
            except Exception as exc:
                LOGGER.debug("google.generativeai candidate %s failed: %s", model_name, exc)
                continue
    except ImportError:
        pass

    return ""


def _heuristic_fallback(text: str) -> Dict[str, Any]:
    raw_text = strip_email_history(text or "")
    t = (raw_text or "").lower()

    if any(word in t for word in ["asap", "today", "immediately", "right now", "urgent", "emergency"]):
        return {"emotion": "urgent", "intensity": 0.88, "confidence": 0.88, "signals": ["Customer expresses urgency."]}
    if any(word in t for word in ["angry", "furious", "worst", "unacceptable", "ridiculous", "disaster"]):
        return {"emotion": "angry", "intensity": 0.9, "confidence": 0.90, "signals": ["Customer expresses strong dissatisfaction."]}
    if any(word in t for word in ["frustrated", "annoyed", "upset", "still waiting", "nobody helping", "three times", "no response"]):
        return {"emotion": "frustrated", "intensity": 0.83, "confidence": 0.85, "signals": ["Customer reports repeated waiting and lack of help."]}
    if any(word in t for word in ["worried", "concerned", "afraid", "scared", "anxious", "trip to", "business trip", "out of town", "missed delivery"]):
        return {"emotion": "worried", "intensity": 0.78, "confidence": 0.85, "signals": ["Customer expresses concern or schedule conflict."]}
    if any(word in t for word in ["what can i do", "what should i do", "confused", "not sure", "dont understand", "how do i", "what can i"]):
        return {"emotion": "confused", "intensity": 0.75, "confidence": 0.80, "signals": ["Customer expresses uncertainty or requests guidance."]}
    if any(word in t for word in ["thanks", "great", "happy", "love", "solved my problem", "awesome", "perfect"]):
        # Check if there is an unresolved problem following polite greeting
        has_issue = any(w in t for w in ["what can", "what should", "help", "partner", "contact me", "not available", "trip", "delay", "issue", "problem"])
        if not has_issue:
            return {"emotion": "satisfied", "intensity": 0.82, "confidence": 0.90, "signals": ["Customer explicitly indicates satisfaction."]}

    return FALLBACK_RESULT.copy()


def _parse_model_json(response_text: str) -> Dict[str, Any]:
    cleaned = clean_response(response_text)
    if not cleaned:
        return FALLBACK_RESULT.copy()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return FALLBACK_RESULT.copy()

    emotion = str(data.get("emotion", "")).strip().lower()
    if emotion not in ALLOWED_EMOTIONS:
        return FALLBACK_RESULT.copy()

    signals = data.get("signals") or []
    if isinstance(signals, str):
        signals = [signals]
    signals_clean = [str(item).strip() for item in signals if str(item).strip()]

    return {
        "emotion": emotion,
        "intensity": _normalize_intensity(data.get("intensity", 0.5)),
        "confidence": _normalize_confidence(data.get("confidence", 0.45)),
        "signals": signals_clean[:3],
    }


def detect_emotion(text: str, history: str = "") -> Dict[str, Any]:
    if not text or not text.strip():
        LOGGER.info("Emotion input text is empty. Falling back to neutral.")
        return FALLBACK_RESULT.copy()

    clean_text_input = strip_email_history(text)
    api_key = os.getenv("GEMINI_API_KEY", "")
    prompt = build_emotion_classifier_prompt(clean_text_input, history=history, taxonomy=list(EMOTION_TAXONOMY))

    if not api_key:
        result = _heuristic_fallback(clean_text_input)
        LOGGER.info("Emotion input=%r | emotion=%s | confidence=%.2f", clean_text_input, result["emotion"], result["confidence"])
        return result

    try:
        response_text = _generate_emotion_gemini(api_key, prompt)
        result = _parse_model_json(response_text)
        if result == FALLBACK_RESULT:
            result = _heuristic_fallback(clean_text_input)
        LOGGER.info("Emotion input=%r | emotion=%s | confidence=%.2f", clean_text_input, result["emotion"], result["confidence"])
        return result
    except Exception as exc:
        LOGGER.warning("Gemini emotion detection failed, using fallback: %s", exc)
        result = _heuristic_fallback(clean_text_input)
        LOGGER.info("Emotion input=%r | emotion=%s | confidence=%.2f", clean_text_input, result["emotion"], result["confidence"])
        return result



def detect_emotion_for_email(email_id: str, text: str) -> Dict[str, Any]:
    result = detect_emotion(text)
    LOGGER.info("email_id=%s | emotion=%s | confidence=%.2f", email_id, result["emotion"], result["confidence"])
    return result


def _confidence_to_float(confidence_value: Any) -> float:
    return _normalize_confidence(confidence_value)


def detect_intent_emotion_gemini(text: str) -> Dict[str, float | str]:
    result = detect_emotion(text)
    return {
        "emotion": result.get("emotion", "neutral"),
        "emotion_confidence": _confidence_to_float(result.get("confidence", 0.45)),
    }
