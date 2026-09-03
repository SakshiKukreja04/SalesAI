"""Email sending logic using Gmail API with SMTP fallback.

Provides outbound email sending for support replies with automatic
fallback to SMTP if Gmail API is unavailable.
"""

import base64
import logging
import os
import re
import smtplib
from email.utils import parseaddr
from email.mime.text import MIMEText
from typing import Optional

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
# pyrefly: ignore [missing-import]
from googleapiclient.discovery import build
# pyrefly: ignore [missing-import]
from googleapiclient.errors import HttpError

from app.config import settings


load_dotenv()
LOGGER = logging.getLogger(__name__)

# Common surname endings used as a fallback for compact email usernames.
COMMON_SURNAME_SUFFIXES = {
    "sinha",
    "singh",
    "sharma",
    "gupta",
    "kumar",
    "verma",
    "mehta",
    "khan",
    "patel",
    "jain",
    "agarwal",
    "agrawal",
    "tiwari",
    "trivedi",
    "chopra",
    "kapoor",
    "malhotra",
    "bhatia",
    "chauhan",
    "yadav",
    "pandey",
    "mishra",
    "saxena",
    "arora",
    "joshi",
    "nair",
    "menon",
    "reddy",
    "iyer",
    "iyengar",
}


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

    # Strip digits and normalize separators into spaces.
    cleaned_local = re.sub(r"\d+", "", email_local_part)
    cleaned_local = re.sub(r"[._\-+]+", " ", cleaned_local).strip()
    cleaned_local = re.sub(r"\s+", " ", cleaned_local)

    # If no separators exist and we detect a repeated boundary letter (e.g. "palakkukreja"),
    # split into two words to improve readability.
    if " " not in cleaned_local:
        duplicate_boundary = re.search(r"([a-zA-Z])\1[a-zA-Z]{4,}$", cleaned_local)
        if duplicate_boundary and duplicate_boundary.start() >= 2:
            split_idx = duplicate_boundary.start() + 1
            cleaned_local = f"{cleaned_local[:split_idx]} {cleaned_local[split_idx:]}"

    # Fallback for compact names like "nihalsinha" -> "nihal sinha".
    # Apply only when we still have a single token and both sides are meaningful.
    if " " not in cleaned_local:
        local_lower = cleaned_local.lower()
        for suffix in COMMON_SURNAME_SUFFIXES:
            if local_lower.endswith(suffix) and len(local_lower) > len(suffix) + 1:
                prefix = cleaned_local[: len(cleaned_local) - len(suffix)]
                if len(prefix) >= 3:
                    cleaned_local = f"{prefix} {cleaned_local[-len(suffix):]}"
                    break

    name_parts = [part for part in cleaned_local.split(" ") if part]
    name = " ".join(part.capitalize() for part in name_parts)
    
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
DEFAULT_SIGNATURE = "Best regards,\nCustomer Support Team\nShopiFyX"


def _with_signature(body: str) -> str:
    """Append configured signature unless it already exists in reply body."""
    content = (body or "").strip()
    raw_signature = (settings.reply_signature or DEFAULT_SIGNATURE).strip()
    signature = raw_signature.replace("\\n", "\n").strip()

    if "best regards" in content.lower() or "customer support team" in content.lower():
        return content

    if not content:
        return signature

    return f"{content}\n\n{signature}"


def _with_customer_greeting(body: str, customer_name: str) -> str:
    """Prefix reply body with a personalized greeting when appropriate."""
    content = (body or "").strip()
    if not content:
        return content

    first_line = content.splitlines()[0].strip().lower()
    if first_line.startswith("hi ") or first_line.startswith("hi,") or first_line.startswith("hello "):
        return content

    safe_name = (customer_name or "").strip()
    if safe_name and safe_name.lower() not in {"valued customer", "customer", "support", "shopifyx", "user", "none", "null"}:
        first_name = safe_name.split()[0].title()
        return f"Hi {first_name},\n\n{content}"

    return f"Hi,\n\n{content}"


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


def _text_to_html_justified(text: str) -> str:
    """Convert plain text email body to HTML with justified alignment."""
    # Escape HTML special characters
    html_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # Convert newlines to <br> and paragraph breaks to <p> tags
    paragraphs = html_text.split("\n\n")
    html_paragraphs = []
    
    for para in paragraphs:
        # Convert single line breaks within paragraph to <br>
        para_html = para.replace("\n", "<br>")
        if para_html.strip():
            html_paragraphs.append(f"<p style='text-align: justify; line-height: 1.6;'>{para_html}</p>")
    
    full_html = "\n".join(html_paragraphs)
    
    # Wrap in basic HTML structure
    return f"""<html>
<body style='font-family: Arial, sans-serif; color: #333;'>
{full_html}
</body>
</html>"""


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
        
        # Convert to HTML with justified text
        html_body = _text_to_html_justified(body)
        message = MIMEText(html_body, "html")
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
    
    # Convert to HTML with justified text
    html_body = _text_to_html_justified(body)
    msg = MIMEText(html_body, "html")
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
    _, parsed_to = parseaddr(to_email)
    recipient = parsed_to or (to_email or "").strip()
    if not recipient:
        LOGGER.error("send_email: Invalid recipient address: %r", to_email)
        return False

    if not customer_name:
        customer_name = extract_customer_name(recipient)

    from app.agents.generator import normalize_customer_response
    final_body = normalize_customer_response(body, customer_name=customer_name)
    final_subject = f"Re: {subject}" if use_reply_prefix and not subject.startswith("Re:") else subject
    
    # Mock mode for development
    if settings.smtp_mock_mode:
        LOGGER.info("[MOCK EMAIL] To: %s | Subject: %s | Customer: %s", recipient, final_subject, customer_name)
        print(f"[MOCK EMAIL] To: {recipient} | Subject: {final_subject} | Customer: {customer_name}\n{final_body}")
        return True
    
    # Try Gmail API first
    if _send_via_gmail_api(recipient, final_subject, final_body):
        return True
    
    # Fall back to SMTP
    LOGGER.info("Gmail API not available; attempting SMTP fallback")
    if _send_via_smtp(recipient, final_subject, final_body):
        return True
    
    LOGGER.error("Failed to send email to %s via both Gmail API and SMTP", recipient)
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

    _, parsed_to = parseaddr(to)
    recipient = parsed_to or (to or "").strip()
    if not recipient:
        LOGGER.error("send_email_reply: Invalid recipient address: %r", to)
        return False

    if settings.smtp_mock_mode:
        LOGGER.info("[MOCK EMAIL] send_email_reply To=%s Subject=%s", recipient, subject)
        return True
    
    if not settings.smtp_email or not settings.smtp_password:
        LOGGER.error(
            "send_email_reply: SMTP credentials not configured. "
            "Set SMTP_EMAIL and SMTP_PASSWORD in .env"
        )
        return False
    
    try:
        # Extract customer name from email if not provided
        if not customer_name:
            customer_name = extract_customer_name(recipient)
        
        # Format subject with "Re: " prefix
        reply_subject = f"Re: {subject}" if not subject.startswith("Re:") else subject
        
        # Format email body using standardized plain-text normalizer
        from app.agents.generator import normalize_customer_response
        formatted_body = normalize_customer_response(body, customer_name=customer_name)
        
        # Create MIME message
        msg = MIMEText(formatted_body)
        msg["Subject"] = reply_subject
        msg["From"] = settings.smtp_email
        msg["To"] = recipient
        
        # Send via SMTP
        LOGGER.debug("Connecting to SMTP server %s:%d", settings.smtp_server, settings.smtp_port)
        
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()
            LOGGER.debug("TLS connection established")
            
            server.login(settings.smtp_email, settings.smtp_password)
            LOGGER.debug("SMTP authentication successful")
            
            server.sendmail(settings.smtp_email, [recipient], msg.as_string())
            LOGGER.info("Email sent successfully to %s", recipient)
        
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
        LOGGER.error("Failed to send email reply to %s: %s", recipient, exc)
        return False

