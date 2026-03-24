"""FastAPI entrypoint for SalesAI email support system."""

import logging
from threading import Thread
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agents.orchestrator import process_email as orchestrator_process_email
from app.config import settings
from app.db.supabase_client import get_email_records
from app.email.fetch_emails import poll_gmail_inbox
from app.rag.chroma_store import ensure_collection, refresh_knowledge_embeddings
from run_email_pipeline import run_email_pipeline


app = FastAPI(title=settings.app_name)
LOGGER = logging.getLogger(__name__)
_email_listener_thread: Thread | None = None

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def start_email_listener() -> None:
    """Run email polling pipeline continuously in background."""
    run_email_pipeline(interval=30, poll_forever=True)


class EmailRequest(BaseModel):
    """Request schema for manually testing one inbound email."""

    customer_email: str
    subject: str
    body: str


@app.on_event("startup")
def startup_event() -> None:
    """Initialize RAG resources and seed default knowledge docs."""
    global _email_listener_thread

    ensure_collection()
    refresh_stats = refresh_knowledge_embeddings("data/knowledge")
    LOGGER.info(
        "Knowledge refresh complete: files=%d chunks=%d deleted=%d",
        refresh_stats.get("files", 0),
        refresh_stats.get("chunks", 0),
        refresh_stats.get("deleted", 0),
    )

    if _email_listener_thread and _email_listener_thread.is_alive():
        return

    LOGGER.info("Starting Email Listener...")
    _email_listener_thread = Thread(target=start_email_listener)
    _email_listener_thread.daemon = True
    _email_listener_thread.start()
    LOGGER.info("Email Listener Running in Background")


@app.get("/health")
def health() -> Dict[str, str]:
    """Simple health endpoint for service checks."""
    return {"status": "ok", "service": settings.app_name}


@app.get("/poll")
def poll() -> List[Dict[str, str]]:
    """Fetch latest inbox messages (mock mode available)."""
    return poll_gmail_inbox()


@app.post("/process-email")
def process_email_endpoint(payload: EmailRequest) -> Dict[str, str]:
    """Run SalesAI full email pipeline through orchestrator process_email."""
    result = orchestrator_process_email(
        {
            "from": payload.customer_email,
            "subject": payload.subject,
            "body": payload.body,
        }
    )

    return result


@app.get("/api/emails")
def get_emails(limit: int = 100) -> Dict[str, Any]:
    """Fetch recent email records for admin dashboard.
    
    Args:
        limit: Maximum number of records to return (default 100)
    
    Returns:
        Dictionary with list of email records
    """
    records = get_email_records(limit=limit)
    return {
        "total": len(records),
        "emails": records
    }
