"""Supabase client and logging helpers.

This module keeps DB concerns separate from business logic.
"""

from typing import Any, Dict, Optional
import importlib

from app.config import settings


_client = None


def get_supabase_client() -> Optional[Any]:
    """Return a Supabase client if credentials are configured."""
    global _client

    if _client is not None:
        return _client

    if not settings.supabase_url or not settings.supabase_key:
        return None

    try:
        supabase_module = importlib.import_module("supabase")
        create_client = getattr(supabase_module, "create_client")
        _client = create_client(settings.supabase_url, settings.supabase_key)
        return _client
    except Exception as exc:
        print(f"Supabase client init failed: {exc}")
        return None


def log_interaction(payload: Dict[str, Any]) -> None:
    """Log a processed email interaction to Supabase or stdout fallback."""
    client = get_supabase_client()

    if client is None:
        print(f"[MOCK SUPABASE LOG] {payload}")
        return

    try:
        client.table(settings.supabase_table).insert(payload).execute()
    except Exception as exc:
        print(f"Supabase log insert failed: {exc}")
