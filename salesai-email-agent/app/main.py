"""FastAPI entrypoint for SalesAI email support system."""

import logging
from threading import Thread
from typing import Dict, List

from fastapi import FastAPI
from pydantic import BaseModel

from app.agents.orchestrator import handle_customer_email
from app.config import settings
from app.email.fetch_emails import poll_gmail_inbox
from app.email.send_email import send_email
from app.rag.chroma_store import ensure_collection, seed_knowledge_from_folder
from run_email_pipeline import run_email_pipeline


app = FastAPI(title=settings.app_name)
LOGGER = logging.getLogger(__name__)
_email_listener_thread: Thread | None = None


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
    seed_knowledge_from_folder("data/knowledge")

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
def process_email(payload: EmailRequest) -> Dict[str, str]:
    """Run full multi-agent flow and optionally send generated reply."""
    result = handle_customer_email(
        customer_email=payload.customer_email,
        subject=payload.subject,
        body=payload.body,
    )

    send_email(
        to_email=payload.customer_email,
        subject=f"Re: {payload.subject}",
        body=result["reply"],
    )

    return result
