"""Strict context prompt builder for customer support generation."""

from typing import List


def build_strict_context_prompt(user_query: str, retrieved_chunks: List[str]) -> str:
    """Build strict prompt that disallows policy hallucination.

    The format intentionally mirrors a deterministic instruction template
    so model behavior remains consistent across providers.
    """
    context_block = "\n\n".join(retrieved_chunks).strip()
    if not context_block:
        context_block = "[NO RELEVANT CONTEXT FOUND]"

    return (
        "You are a customer support assistant.\n"
        "You must answer using the provided context.\n"
        "If relevant context is present, DO NOT say 'I do not know'.\n"
        "Only say 'I do not know' if context is completely unrelated.\n"
        "Do NOT make up policies.\n\n"
        "Context:\n"
        f"{context_block}\n\n"
        "Question:\n"
        f"{(user_query or '').strip()}\n\n"
        "Answer strictly from context:"
    )
