"""Email sending logic using Gmail API with SMTP fallback.

Provides outbound email sending for support replies with automatic
fallback to SMTP if Gmail API is unavailable.
"""

import base64
import logging
import os
import smtplib
from email.mime.text import MIMEText
from typing import Optional

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings


load_dotenv()
LOGGER = logging.getLogger(__name__)


def extract_customer_name(from_header: str) -> str:
    """Extract customer name from email From header.
    
    Handles multiple formats:
    - "John Doe <john.doe@example.com>" -> "John Doe"
    - "<john.doe@example.com>" -> "john.doe" (formatted)
    - "john.doe@example.com" -> "john.doe" (formatted)
    - "John.Doe@example.com" -> "John Doe" (with capitals)
    
    Args:
        from_header: Raw From header value
    
    Returns:
        Extracted and formatted customer name, or "Valued Customer" if extraction fails
    """
    if not from_header:
        return "Valued Customer"
    
    # Try to extract name from "Name <email@domain.com>" format
    angle_bracket_idx = from_header.find("<")
    if angle_bracket_idx > 0:
        name_part = from_header[:angle_bracket_idx].strip()
        if name_part and name_part not in {"", '"'}:
            return name_part.strip('"').strip()
    
    # Extract email and format as name
    email_match = from_header.split("<")[-1].rstrip(">").strip()
    if not email_match or "@" not in email_match:
        return "Valued Customer"
    
    email_local_part = email_match.split("@")[0]
    
    # Handle common formats: john.doe, john_doe, johndoe
    if "." in email_local_part:
        name_parts = email_local_part.split(".")
        name = " ".join(part.capitalize() for part in name_parts)
    elif "_" in email_local_part:
        name_parts = email_local_part.split("_")
        name = " ".join(part.capitalize() for part in name_parts)
    else:
        name = email_local_part.capitalize()
    
    return name if name else "Valued Customer"


GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
GMAIL_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", os.getenv("GMAIL_CREDENTIALS_PATH", ""))
GMAIL_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", os.getenv("GMAIL_TOKEN_PATH", ""))

# SMTP Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# Optional convenience variables
EMAIL_ADDRESS = os.getenv("SMTP_EMAIL")
EMAIL_PASSWORD = os.getenv("SMTP_PASSWORD")

# Email signature
DEFAULT_SIGNATURE = "Best regards,\nShopiFyX Support Team"


def _with_signature(body: str) -> str:
    """Append configured signature unless it already exists in reply body."""
    content = (body or "").strip()
    signature = (settings.reply_signature or "").strip()
    if not signature:
        return content

    if signature.lower() in content.lower():
        return content

    if not content:
        return signature

    return f"{content}\n\n{signature}"


def _get_gmail_service() -> Optional[object]:
    """Get authenticated Gmail API service client.
    
    Returns:
        Gmail service object if authentication succeeds, None otherwise.
    """
    try:
        if not GMAIL_TOKEN_PATH:
            LOGGER.debug("Gmail token path not configured; Gmail API unavailable")
            return None
        
        if not os.path.exists(GMAIL_TOKEN_PATH):
            LOGGER.debug("Gmail token file not found; Gmail API unavailable")
            return None
        
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, GMAIL_SCOPES)
        
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        
        service = build("gmail", "v1", credentials=creds)
        return service
        
    except Exception as exc:
        LOGGER.debug("Gmail service initialization failed: %s", exc)
        return None


def _send_via_gmail_api(to_email: str, subject: str, body: str) -> bool:
    """Send email through Gmail API.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body (with signature appended)
    
    Returns:
        True if sent successfully, False otherwise.
    """
    try:
        service = _get_gmail_service()
        if service is None:
            return False
        
        from_email = settings.smtp_email or os.getenv("GOOGLE_AUTH_EMAIL", "")
        if not from_email:
            LOGGER.warning("SMTP_EMAIL or GOOGLE_AUTH_EMAIL not configured for Gmail API")
            return False
        
        message = MIMEText(body)
        message["to"] = to_email
        message["from"] = from_email
        message["subject"] = subject
        
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_message = {"raw": raw_message}
        
        service.users().messages().send(userId="me", body=send_message).execute()
        LOGGER.info("Email sent via Gmail API to %s", to_email)
        return True
        
    except HttpError as exc:
        LOGGER.error("Gmail API error: %s", exc)
        return False
    except Exception as exc:
        LOGGER.error("Failed to send via Gmail API: %s", exc)
        return False


def _send_via_smtp(to_email: str, subject: str, body: str) -> bool:
    """Send email through SMTP server.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body (with signature appended)
    
    Returns:
        True if sent successfully, False otherwise.
    """
    if not settings.smtp_email or not settings.smtp_password:
        LOGGER.error("SMTP_EMAIL/SMTP_PASSWORD are required for SMTP sending")
        return False
    
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_email
    msg["To"] = to_email
    
    try:
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_email, settings.smtp_password)
            server.sendmail(settings.smtp_email, [to_email], msg.as_string())
        LOGGER.info("Email sent via SMTP to %s", to_email)
        return True
    except Exception as exc:
        LOGGER.error("SMTP send failed: %s", exc)
        return False



def send_email(to_email: str, subject: str, body: str, use_reply_prefix: bool = True, customer_name: str = "") -> bool:
    """Send an email using Gmail API with SMTP fallback.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body
        use_reply_prefix: If True, prepend "Re: " to subject (for replies)
        customer_name: Customer's name for personalized message. If empty, extracted from to_email
    
    Returns:
        True if email was sent successfully, False otherwise.
    """
    final_body = _with_signature(body)
    final_subject = f"Re: {subject}" if use_reply_prefix and not subject.startswith("Re:") else subject
    
    # Extract customer name if not provided
    if not customer_name:
        customer_name = extract_customer_name(to_email)
    
    # Mock mode for development
    if settings.smtp_mock_mode:
        LOGGER.info("[MOCK EMAIL] To: %s | Subject: %s | Customer: %s", to_email, final_subject, customer_name)
        print(f"[MOCK EMAIL] To: {to_email} | Subject: {final_subject} | Customer: {customer_name}\n{final_body}")
        return True
    
    # Try Gmail API first
    if _send_via_gmail_api(to_email, final_subject, final_body):
        return True
    
    # Fall back to SMTP
    LOGGER.info("Gmail API not available; attempting SMTP fallback")
    if _send_via_smtp(to_email, final_subject, final_body):
        return True
    
    LOGGER.error("Failed to send email to %s via both Gmail API and SMTP", to_email)
    return False


def send_email_reply(to: str, subject: str, body: str, customer_name: str = "") -> bool:
    """Send a customer support reply email via SMTP.
    
    Specialized function for sending reply emails to customers.
    - Automatically adds "Re: " to subject if not already present
    - Formats email with professional signature
    - Uses customer's actual name in greeting
    - Uses SMTP for reliable delivery
    - Comprehensive error handling and logging
    
    Args:
        to: Recipient email address (customer email)
        subject: Email subject line (original subject, "Re: " added automatically)
        body: Generated reply body text
        customer_name: Customer's name for personalized greeting. If empty, extracted from `to` email
    
    Returns:
        True if email sent successfully, False otherwise
    
    Example:
        success = send_email_reply(
            to="customer@example.com",
            subject="Order Status Inquiry",
            body="Your order is being processed and will ship tomorrow.",
            customer_name="John Doe"
        )
    """
    if not to or not subject or not body:
        LOGGER.error("send_email_reply: Missing required arguments (to, subject, body)")
        return False
    
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        LOGGER.error(
            "send_email_reply: SMTP credentials not configured. "
            "Set SMTP_EMAIL and SMTP_PASSWORD in .env"
        )
        return False
    
    try:
        # Extract customer name from email if not provided
        if not customer_name:
            customer_name = extract_customer_name(to)
        
        # Format subject with "Re: " prefix
        reply_subject = f"Re: {subject}" if not subject.startswith("Re:") else subject
        
        # Format email body with personalized greeting and signature
        formatted_body = f"""Hi {customer_name},

{body}

{DEFAULT_SIGNATURE}
"""
        
        # Create MIME message
        msg = MIMEText(formatted_body)
        msg["Subject"] = reply_subject
        msg["From"] = SMTP_EMAIL
        msg["To"] = to
        
        # Send via SMTP
        LOGGER.debug("Connecting to SMTP server %s:%d", SMTP_SERVER, SMTP_PORT)
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            LOGGER.debug("TLS connection established")
            
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            LOGGER.debug("SMTP authentication successful")
            
            server.sendmail(SMTP_EMAIL, [to], msg.as_string())
            LOGGER.info("Email sent successfully to %s", to)
        
        return True
        
    except smtplib.SMTPAuthenticationError as exc:
        LOGGER.error(
            "SMTP authentication failed: Invalid email or password. "
            "Verify SMTP_EMAIL and SMTP_PASSWORD in .env"
        )
        return False
        
    except smtplib.SMTPException as exc:
        LOGGER.error("SMTP error: %s", exc)
        return False
        
    except Exception as exc:
        LOGGER.error("Failed to send email reply to %s: %s", to, exc)
        return False

