"""FastAPI entrypoint for SalesAI email support system."""

import base64
import json
import logging
from threading import Thread
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.agents.orchestrator import process_email as orchestrator_process_email
from app.config import settings
from app.db.supabase_client import (
    activate_app_user,
    create_or_update_admin_user,
    get_app_user_by_email,
    get_email_records,
    invite_user,
)
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


class CreateUserRequest(BaseModel):
    email: str
    name: str = ""
    business_id: str = ""
    role: str = "admin"


class InviteUserRequest(BaseModel):
    name: str
    email: str
    role: str = "manager"
    business_id: str
    assigned_intents: List[str] = []


class ActivateUserRequest(BaseModel):
    email: str
    firebase_uid: str = ""


def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def _auth_header_to_token(authorization: str) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def verify_firebase_user(authorization: str = Header(default="")) -> Dict[str, Any]:
    """Verify Firebase JWT and return claims."""
    token = _auth_header_to_token(authorization)

    try:
        verify_kwargs: Dict[str, Any] = {}
        if settings.firebase_project_id:
            verify_kwargs["audience"] = settings.firebase_project_id

        claims = id_token.verify_firebase_token(
            token,
            google_requests.Request(),
            **verify_kwargs,
        )
    except Exception as exc:
        if not settings.allow_insecure_dev_auth:
            raise HTTPException(status_code=401, detail="Invalid Firebase token") from exc

        # Local development fallback: decode JWT payload without signature verification.
        try:
            payload_part = token.split(".")[1]
            padded = payload_part + "=" * (-len(payload_part) % 4)
            decoded_bytes = base64.urlsafe_b64decode(padded.encode("utf-8"))
            claims = json.loads(decoded_bytes.decode("utf-8"))
        except Exception as decode_exc:
            raise HTTPException(status_code=401, detail="Invalid Firebase token") from decode_exc

    if not claims:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return claims


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

    normalized = dict(result)
    for key in ("intent_confidence", "emotion_intensity"):
        if key in normalized:
            normalized[key] = str(normalized[key])
    if "grounded" in normalized:
        normalized["grounded"] = str(bool(normalized["grounded"]))
    if "human_review_required" in normalized:
        normalized["human_review_required"] = str(bool(normalized["human_review_required"]))

    return normalized


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


@app.post("/api/create-user")
def create_user(payload: CreateUserRequest, claims: Dict[str, Any] = Depends(verify_firebase_user)) -> Dict[str, Any]:
    """Create first-party admin record after Firebase signup."""
    requested_email = _normalize_email(payload.email)
    token_email = _normalize_email(str(claims.get("email", "")))

    if requested_email != token_email:
        raise HTTPException(status_code=403, detail="Email mismatch between token and payload")

    if (payload.role or "admin").strip().lower() != "admin":
        raise HTTPException(status_code=400, detail="Only admin role can use create-user")

    try:
        user = create_or_update_admin_user(
            email=requested_email,
            name=payload.name,
            business_id=payload.business_id,
            firebase_uid=str(claims.get("user_id", "")) or str(claims.get("uid", "")),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to create admin user") from exc

    return {"user": user}


@app.post("/api/invite-user")
def invite_user_endpoint(
    payload: InviteUserRequest,
    claims: Dict[str, Any] = Depends(verify_firebase_user),
) -> Dict[str, Any]:
    """Invite a new team member. Requester must be active admin in backend DB."""
    inviter_email = _normalize_email(str(claims.get("email", "")))
    inviter = get_app_user_by_email(inviter_email)

    if not inviter or inviter.get("role") != "admin" or inviter.get("status") != "active":
        raise HTTPException(status_code=403, detail="Only active admins can invite users")

    role = (payload.role or "manager").strip().lower()
    if role != "manager":
        raise HTTPException(status_code=400, detail="Invited user role must be manager")
    if not payload.assigned_intents:
        raise HTTPException(status_code=400, detail="assigned_intents must include at least one intent")

    try:
        user = invite_user(
            name=payload.name,
            email=payload.email,
            role=role,
            business_id=payload.business_id,
            assigned_intents=payload.assigned_intents,
            invited_by=inviter_email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to invite user") from exc

    invite_link = f"/signup?email={user['email']}&invite=true"
    return {"user": user, "invite_link": invite_link}


@app.get("/api/get-user")
def get_user(
    email: str = Query(..., description="User email"),
    claims: Dict[str, Any] = Depends(verify_firebase_user),
) -> Dict[str, Any]:
    """Fetch backend role/intents for authenticated user."""
    requested_email = _normalize_email(email)
    token_email = _normalize_email(str(claims.get("email", "")))

    if requested_email != token_email:
        raise HTTPException(status_code=403, detail="Email mismatch between token and query")

    user = get_app_user_by_email(requested_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"user": user}


@app.get("/api/invite-status")
def get_invite_status(email: str = Query(..., description="Invitee email")) -> Dict[str, Any]:
    """Public endpoint to validate if an email is invited before signup."""
    requested_email = _normalize_email(email)
    user = get_app_user_by_email(requested_email)
    if not user:
        return {"invited": False}

    is_invited = user.get("status") in {"invited", "active"}
    return {
        "invited": is_invited,
        "email": user.get("email"),
        "role": user.get("role"),
        "business_id": user.get("business_id"),
        "assigned_intents": user.get("assigned_intents") or [],
        "status": user.get("status"),
    }


@app.post("/api/activate-user")
def activate_user(
    payload: ActivateUserRequest,
    claims: Dict[str, Any] = Depends(verify_firebase_user),
) -> Dict[str, Any]:
    """Activate invited user after Firebase signup."""
    requested_email = _normalize_email(payload.email)
    token_email = _normalize_email(str(claims.get("email", "")))

    if requested_email != token_email:
        raise HTTPException(status_code=403, detail="Email mismatch between token and payload")

    existing = get_app_user_by_email(requested_email)
    if not existing:
        raise HTTPException(status_code=403, detail="You are not invited")
    if existing.get("role") != "manager":
        raise HTTPException(status_code=400, detail="activate-user is only for invited manager accounts")
    if existing.get("status") not in {"invited", "active"}:
        raise HTTPException(status_code=400, detail="Invalid user status for activation")

    activated = activate_app_user(
        email=requested_email,
        firebase_uid=payload.firebase_uid or str(claims.get("user_id", "")) or str(claims.get("uid", "")),
    )
    if not activated:
        raise HTTPException(status_code=500, detail="Failed to activate user")

    return {"user": activated}
