"""Text preprocessing utilities for incoming customer emails."""

import re


def preprocess_text(text: str) -> str:
    """Clean email text with lightweight normalization steps."""
    lowered = text.lower().strip()
    lowered = re.sub(r"\s+", " ", lowered)
    cleaned = re.sub(r"[^a-z0-9\s.,!?-]", "", lowered)
    return cleaned
