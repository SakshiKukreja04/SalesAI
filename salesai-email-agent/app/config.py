"""Application configuration utilities.

This module centralizes environment-variable loading and exposes a small
settings object used by the rest of the project.
"""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    """Container for app settings loaded from environment variables."""

    app_name: str = os.getenv("APP_NAME", "SalesAI Email Agent")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))

    gmail_credentials_path: str = os.getenv("GMAIL_CREDENTIALS_PATH", "")
    gmail_token_path: str = os.getenv("GMAIL_TOKEN_PATH", "")

    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_email: str = os.getenv("SMTP_EMAIL", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_mock_mode: bool = os.getenv("SMTP_MOCK_MODE", "true").strip().lower() == "true"
    reply_signature: str = os.getenv("REPLY_SIGNATURE", "Best regards,\nCustomer Support Team")

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    chroma_path: str = os.getenv("CHROMA_PATH", "./data/chroma")
    chroma_collection: str = os.getenv("CHROMA_COLLECTION", "salesai_knowledge")
    chroma_reply_collection: str = os.getenv("CHROMA_REPLY_COLLECTION", "salesai_reply_memory")

    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    supabase_table: str = os.getenv("SUPABASE_TABLE", "email_logs")

    supabase_db_url: str = os.getenv("SUPABASE_DB_URL", "")


def get_env_var(name: str, default: str = "") -> str:
    """Get an environment variable with an optional default value."""
    return os.getenv(name, default)


settings = Settings()
