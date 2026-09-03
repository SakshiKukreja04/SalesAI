"""Prompt builder for emotion detection."""

EMOTION_TAXONOMY = [
    "neutral",
    "happy",
    "satisfied",
    "confused",
    "frustrated",
    "angry",
    "disappointed",
    "worried",
    "urgent",
]


def build_emotion_classifier_prompt(message: str, history: str = "", taxonomy: list[str] | None = None) -> str:
    """Return the centralized prompt used for emotion detection."""
    allowed = taxonomy or EMOTION_TAXONOMY
    history_block = history.strip()
    history_text = f"\nConversation history:\n{history_block}\n" if history_block else ""
    return (
        "You are the Customer Emotion Detection module of ShopiFyX SalesAI.\n\n"
        "Analyze the customer's emotional state from the current message\n"
        "and available conversation history.\n\n"
        "Allowed emotions:\n"
        + "- " + "\n- ".join(allowed) + "\n\n"
        + "Rules:\n"
        + "1. Identify the customer's dominant emotion.\n"
        + "2. Do not confuse the customer's problem with their emotion.\n"
        + "3. 'Refund request' is an intent, not an emotion.\n"
        + "4. Use the wording, punctuation, repeated complaints, urgency,\n"
        + "   and conversation context as signals.\n"
        + "5. Do not infer sensitive personal attributes.\n"
        + "6. If there is insufficient emotional evidence, use 'neutral'.\n"
        + "7. Do not generate a response.\n\n"
        + "Return ONLY valid JSON:\n\n"
        + "{\n"
        + '  "emotion": "<one_emotion>",\n'
        + '  "intensity": 0.0,\n'
        + '  "confidence": 0.0,\n'
        + '  "signals": ["<short observable signal>"]\n'
        + "}\n\n"
        + history_text
        + "Customer message:\n"
        + message
        + "\n"
    )
