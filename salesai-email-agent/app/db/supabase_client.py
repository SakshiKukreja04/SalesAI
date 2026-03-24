import logging
import os
from typing import Dict, Any, Optional

from dotenv import load_dotenv

try:
    import psycopg2
    from psycopg2 import DatabaseError, OperationalError
except ImportError:  # pragma: no cover - environment-dependent import
    psycopg2 = None

    class DatabaseError(Exception):
        """Fallback DB error type when psycopg2 is unavailable."""

    class OperationalError(Exception):
        """Fallback operational error type when psycopg2 is unavailable."""


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def map_confidence(conf: Any) -> float:
    """Convert confidence labels or numeric-like inputs to a DB-safe float."""
    mapping = {
        "high": 0.9,
        "medium": 0.6,
        "low": 0.3,
    }

    if conf is None:
        return 0.5

    if isinstance(conf, (int, float)):
        return float(conf)

    key = str(conf).strip().lower()
    if key in mapping:
        return mapping[key]

    try:
        return float(key)
    except ValueError:
        return 0.5


def _load_env() -> None:
    """Load environment variables from a .env file once."""
    if not getattr(_load_env, "loaded", False):
        load_dotenv()
        _load_env.loaded = True


def get_connection() -> Optional[Any]:
    """Create and return a PostgreSQL connection from environment variables."""
    _load_env()

    if psycopg2 is None:
        logger.warning(
            "psycopg2 is not installed. Install dependencies from requirements.txt to enable DB logging."
        )
        return None

    db_url = os.getenv("SUPABASE_DB_URL") or os.getenv("SUPABASE_URL")
    if not db_url:
        logger.error("SUPABASE_DB_URL or SUPABASE_URL is not set in environment variables")
        return None

    try:
        conn = psycopg2.connect(dsn=db_url)
        logger.debug("PostgreSQL connection established")
        return conn
    except OperationalError as exc:
        logger.exception("Failed to connect to PostgreSQL database")
        return None


def create_table_if_not_exists() -> None:
    """Create the customer_emails table if it does not already exist."""
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Database connection could not be established")

    create_table_query = """
    CREATE TABLE IF NOT EXISTS customer_emails (
        id SERIAL PRIMARY KEY,
        email_id TEXT,
        sender_email TEXT,
        subject TEXT,
        body TEXT,
        intent TEXT,
        emotion TEXT,
        timestamp TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    create_index_query = """
    CREATE INDEX IF NOT EXISTS idx_customer_emails_email_id
    ON customer_emails (email_id)
    """

    create_idempotency_table_query = """
    CREATE TABLE IF NOT EXISTS email_processing_state (
        email_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        last_error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    create_idempotency_index_query = """
    CREATE INDEX IF NOT EXISTS idx_email_processing_state_status
    ON email_processing_state (status)
    """

    try:
        with conn.cursor() as cursor:
            cursor.execute(create_table_query)
            cursor.execute(create_index_query)
            cursor.execute(create_idempotency_table_query)
            cursor.execute(create_idempotency_index_query)
        conn.commit()
        logger.info("Ensured customer_emails and email_processing_state tables exist")
    except DatabaseError:
        conn.rollback()
        logger.exception("Error while creating customer_emails table")
        raise
    finally:
        conn.close()
        logger.debug("PostgreSQL connection closed after create_table_if_not_exists")


def insert_email_data(email_data: Dict[str, Any]) -> bool:
    """Insert a single email record into the customer_emails table.

    Expected payload:
        {
            "id": "...",
            "from": "...",
            "subject": "...",
            "body": "...",
            "timestamp": "...",
            "intent": "...",
            "emotion": "..."
        }
    """
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Database connection could not be established")

    insert_query = """
    INSERT INTO customer_emails (
        email_id,
        sender_email,
        subject,
        body,
        intent,
        emotion,
        timestamp
    )
    SELECT %s, %s, %s, %s, %s, %s, %s
    WHERE NOT EXISTS (
        SELECT 1
        FROM customer_emails
        WHERE email_id = %s
    )
    """

    values = (
        email_data.get("id"),
        email_data.get("from"),
        email_data.get("subject"),
        email_data.get("body"),
        email_data.get("intent"),
        email_data.get("emotion"),
        email_data.get("timestamp"),
        email_data.get("id"),
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(insert_query, values)
            inserted = cursor.rowcount > 0
        conn.commit()
        if inserted:
            logger.info("Email data inserted into customer_emails table")
        else:
            logger.info("Skipped duplicate email_id=%s", email_data.get("id"))
        return inserted
    except DatabaseError:
        conn.rollback()
        logger.exception("Failed to insert email data")
        raise
    finally:
        conn.close()
        logger.debug("PostgreSQL connection closed after insert_email_data")


def _create_interactions_table_if_not_exists(
    conn: Any,
) -> None:
    """Ensure the interactions table exists before inserts."""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS customer_interactions (
        id SERIAL PRIMARY KEY,
        customer_email TEXT,
        subject TEXT,
        intent TEXT,
        intent_confidence DOUBLE PRECISION,
        emotion TEXT,
        emotion_confidence DOUBLE PRECISION,
        strategy TEXT,
        reply TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    with conn.cursor() as cursor:
        cursor.execute(create_table_query)


def log_interaction(interaction: Dict[str, Any]) -> None:
    """Persist a generated interaction, with fallback logging when DB is unavailable."""
    conn = get_connection()
    if conn is None:
        logger.warning("DB unavailable. Interaction fallback log: %s", interaction)
        return

    insert_query = """
    INSERT INTO customer_interactions (
        customer_email,
        subject,
        intent,
        intent_confidence,
        emotion,
        emotion_confidence,
        strategy,
        reply
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """

    values = (
        interaction.get("customer_email"),
        interaction.get("subject"),
        interaction.get("intent"),
        map_confidence(interaction.get("intent_confidence")),
        interaction.get("emotion"),
        map_confidence(interaction.get("emotion_confidence")),
        interaction.get("strategy"),
        interaction.get("reply"),
    )

    try:
        _create_interactions_table_if_not_exists(conn)
        with conn.cursor() as cursor:
            cursor.execute(insert_query, values)
        conn.commit()
        logger.info("Interaction logged to customer_interactions table")
    except DatabaseError:
        conn.rollback()
        logger.exception("Failed to persist interaction. Fallback log: %s", interaction)
    finally:
        conn.close()
        logger.debug("PostgreSQL connection closed after log_interaction")


def _create_email_records_table_if_not_exists(conn: Any) -> None:
    """Ensure the email_records table exists for email processing tracking."""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS email_records (
        id SERIAL PRIMARY KEY,
        sender TEXT,
        subject TEXT,
        body TEXT,
        intent TEXT,
        emotion TEXT,
        reply TEXT,
        confidence DOUBLE PRECISION,
        status TEXT,
        escalation_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    
    create_index_query = """
    CREATE INDEX IF NOT EXISTS idx_email_records_status
    ON email_records (status)
    """
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(create_table_query)
            cursor.execute(create_index_query)
        conn.commit()
        logger.debug("Email records table ensured")
    except DatabaseError as exc:
        conn.rollback()
        logger.error("Failed to create email_records table: %s", exc)
        raise


def save_email_record(
    sender: str,
    subject: str,
    body: str,
    intent: str,
    emotion: str,
    reply: str,
    status: str,
    confidence: float = 0.0,
    escalation_reason: str = "",
) -> bool:
    """Save email processing record to database.
    
    Args:
        sender: Customer email address
        subject: Email subject
        body: Email body
        intent: Classified intent
        emotion: Detected emotion
        reply: Generated reply
        status: Processing status ("replied", "escalated", "failed")
        confidence: Confidence score of the reply
        escalation_reason: Reason for escalation (if applicable)
    
    Returns:
        True if record was saved successfully, False otherwise.
    """
    if status not in {"replied", "escalated", "failed"}:
        logger.error("Invalid status '%s'; must be one of: replied, escalated, failed", status)
        return False
    
    conn = get_connection()
    if conn is None:
        logger.warning(
            "DB unavailable. Email record fallback log: sender=%s, status=%s",
            sender,
            status,
        )
        return False
    
    insert_query = """
    INSERT INTO email_records (
        sender,
        subject,
        body,
        intent,
        emotion,
        reply,
        confidence,
        status,
        escalation_reason
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    values = (
        sender,
        subject,
        body,
        intent,
        emotion,
        reply,
        confidence,
        status,
        escalation_reason,
    )
    
    try:
        _create_email_records_table_if_not_exists(conn)
        with conn.cursor() as cursor:
            cursor.execute(insert_query, values)
        conn.commit()
        logger.info("Email record saved (sender=%s, status=%s)", sender, status)
        return True
    except DatabaseError as exc:
        conn.rollback()
        logger.error("Failed to save email record: %s", exc)
        return False
    finally:
        conn.close()
        logger.debug("PostgreSQL connection closed after save_email_record")


def get_email_records(limit: int = 100) -> list[dict]:
    """Fetch recent email records from the email_records table.
    
    Args:
        limit: Maximum number of records to fetch (default 100)
    
    Returns:
        List of email records sorted by creation time (newest first)
    """
    conn = get_connection()
    if conn is None:
        logger.warning("DB unavailable. Cannot fetch email records")
        return []
    
    query = """
    SELECT 
        id,
        sender,
        subject,
        body,
        intent,
        emotion,
        reply,
        confidence,
        status,
        escalation_reason,
        created_at
    FROM email_records
    ORDER BY created_at DESC
    LIMIT %s
    """
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
        
        records = []
        for row in rows:
            records.append({
                "id": row[0],
                "sender": row[1],
                "subject": row[2],
                "body": row[3],
                "intent": row[4],
                "emotion": row[5],
                "reply": row[6],
                "confidence": row[7],
                "status": row[8],
                "escalation_reason": row[9],
                "timestamp": row[10].isoformat() if row[10] else ""
            })
        
        logger.debug("Fetched %d email records from database", len(records))
        return records
    
    except DatabaseError as exc:
        logger.error("Failed to fetch email records: %s", exc)
        return []
    finally:
        conn.close()
        logger.debug("PostgreSQL connection closed after get_email_records")


def check_email_already_replied(email_id: str) -> bool:
    """Return True when an email has already been replied and must be skipped."""
    if not email_id:
        return False

    conn = get_connection()
    if conn is None:
        logger.warning("DB unavailable in check_email_already_replied(email_id=%s)", email_id)
        return False

    query = """
    SELECT status
    FROM email_processing_state
    WHERE email_id = %s
    LIMIT 1
    """

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (email_id,))
            row = cursor.fetchone()
        return bool(row and row[0] == "replied")
    except DatabaseError as exc:
        logger.error("Failed check_email_already_replied for email_id=%s: %s", email_id, exc)
        return False
    finally:
        conn.close()


def reserve_email_for_processing(email_id: str) -> bool:
    """Atomically reserve an email for processing to prevent duplicate workers.

    Returns True only for the worker that successfully inserts the reservation.
    """
    if not email_id:
        return False

    conn = get_connection()
    if conn is None:
        logger.warning("DB unavailable in reserve_email_for_processing(email_id=%s)", email_id)
        return False

    insert_query = """
    INSERT INTO email_processing_state (email_id, status)
    VALUES (%s, 'processing')
    ON CONFLICT (email_id) DO NOTHING
    """

    select_query = """
    SELECT status
    FROM email_processing_state
    WHERE email_id = %s
    LIMIT 1
    """

    try:
        with conn.cursor() as cursor:
            cursor.execute(insert_query, (email_id,))
            inserted = cursor.rowcount > 0
            if not inserted:
                cursor.execute(select_query, (email_id,))
                row = cursor.fetchone()
                existing_status = row[0] if row else "unknown"
                logger.info(
                    "Skipping email_id=%s (already reserved with status=%s)",
                    email_id,
                    existing_status,
                )
        conn.commit()
        return inserted
    except DatabaseError as exc:
        conn.rollback()
        logger.error("Failed reserve_email_for_processing for email_id=%s: %s", email_id, exc)
        return False
    finally:
        conn.close()


def update_email_processing_status(email_id: str, status: str, last_error: str = "") -> bool:
    """Update durable processing status for an email id."""
    if not email_id:
        return False

    allowed = {"processing", "replied", "failed", "escalated"}
    if status not in allowed:
        logger.error("Invalid status=%s for email_id=%s", status, email_id)
        return False

    conn = get_connection()
    if conn is None:
        logger.warning("DB unavailable in update_email_processing_status(email_id=%s)", email_id)
        return False

    query = """
    UPDATE email_processing_state
    SET status = %s,
        last_error = %s,
        updated_at = CURRENT_TIMESTAMP
    WHERE email_id = %s
    """

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (status, (last_error or "")[:1000], email_id))
            updated = cursor.rowcount > 0
        conn.commit()
        return updated
    except DatabaseError as exc:
        conn.rollback()
        logger.error("Failed update_email_processing_status for email_id=%s: %s", email_id, exc)
        return False
    finally:
        conn.close()


def get_replied_email_ids(limit: int = 5000) -> set[str]:
    """Load replied email IDs for fast in-memory duplicate short-circuit."""
    conn = get_connection()
    if conn is None:
        logger.warning("DB unavailable in get_replied_email_ids")
        return set()

    query = """
    SELECT email_id
    FROM email_processing_state
    WHERE status = 'replied'
    ORDER BY updated_at DESC
    LIMIT %s
    """

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
        return {row[0] for row in rows if row and row[0]}
    except DatabaseError as exc:
        logger.error("Failed get_replied_email_ids: %s", exc)
        return set()
    finally:
        conn.close()


def _create_app_users_table_if_not_exists(conn: Any) -> None:
    """Ensure app_users table exists for role-based access and invite workflow."""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS app_users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        name TEXT,
        role TEXT NOT NULL,
        business_id TEXT NOT NULL,
        assigned_intents TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
        status TEXT NOT NULL,
        firebase_uid TEXT,
        invited_by TEXT,
        invited_at TIMESTAMP,
        activated_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """

    create_email_index_query = """
    CREATE INDEX IF NOT EXISTS idx_app_users_email
    ON app_users (email)
    """

    create_business_index_query = """
    CREATE INDEX IF NOT EXISTS idx_app_users_business_id
    ON app_users (business_id)
    """

    create_status_index_query = """
    CREATE INDEX IF NOT EXISTS idx_app_users_status
    ON app_users (status)
    """

    with conn.cursor() as cursor:
        cursor.execute(create_table_query)
        cursor.execute(create_email_index_query)
        cursor.execute(create_business_index_query)
        cursor.execute(create_status_index_query)


def create_or_update_admin_user(
    *,
    email: str,
    name: str,
    business_id: str,
    firebase_uid: str,
) -> Dict[str, Any]:
    """Create or update an admin user record during bootstrap signup."""
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Database connection could not be established")

    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        raise ValueError("email is required")

    query = """
    INSERT INTO app_users (
        email,
        name,
        role,
        business_id,
        assigned_intents,
        status,
        firebase_uid,
        activated_at,
        updated_at
    ) VALUES (%s, %s, 'admin', %s, %s, 'active', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT (email)
    DO UPDATE SET
        name = EXCLUDED.name,
        role = 'admin',
        business_id = EXCLUDED.business_id,
        assigned_intents = EXCLUDED.assigned_intents,
        status = 'active',
        firebase_uid = EXCLUDED.firebase_uid,
        activated_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    RETURNING email, name, role, business_id, assigned_intents, status, firebase_uid
    """

    try:
        _create_app_users_table_if_not_exists(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                query,
                (
                    normalized_email,
                    (name or "").strip() or normalized_email,
                    (business_id or "").strip() or normalized_email,
                    ["ALL"],
                    (firebase_uid or "").strip() or None,
                ),
            )
            row = cursor.fetchone()
        conn.commit()
        return {
            "email": row[0],
            "name": row[1],
            "role": row[2],
            "business_id": row[3],
            "assigned_intents": row[4] or [],
            "status": row[5],
            "firebase_uid": row[6],
        }
    except DatabaseError as exc:
        conn.rollback()
        logger.error("Failed create_or_update_admin_user(email=%s): %s", normalized_email, exc)
        raise
    finally:
        conn.close()


def invite_user(
    *,
    name: str,
    email: str,
    role: str,
    business_id: str,
    assigned_intents: list[str],
    invited_by: str,
) -> Dict[str, Any]:
    """Create or refresh an invited user record."""
    conn = get_connection()
    if conn is None:
        raise RuntimeError("Database connection could not be established")

    normalized_email = (email or "").strip().lower()
    normalized_role = "manager" if role != "admin" else "admin"
    normalized_business_id = (business_id or "").strip()
    if not normalized_email:
        raise ValueError("email is required")
    if not normalized_business_id:
        raise ValueError("business_id is required")

    intents = [item.strip() for item in (assigned_intents or []) if item and item.strip()]
    if normalized_role == "admin":
        intents = ["ALL"]

    query = """
    INSERT INTO app_users (
        email,
        name,
        role,
        business_id,
        assigned_intents,
        status,
        invited_by,
        invited_at,
        updated_at
    ) VALUES (%s, %s, %s, %s, %s, 'invited', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT (email)
    DO UPDATE SET
        name = EXCLUDED.name,
        role = EXCLUDED.role,
        business_id = EXCLUDED.business_id,
        assigned_intents = EXCLUDED.assigned_intents,
        status = 'invited',
        invited_by = EXCLUDED.invited_by,
        invited_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    RETURNING email, name, role, business_id, assigned_intents, status
    """

    try:
        _create_app_users_table_if_not_exists(conn)
        with conn.cursor() as cursor:
            cursor.execute(
                query,
                (
                    normalized_email,
                    (name or "").strip() or normalized_email,
                    normalized_role,
                    normalized_business_id,
                    intents,
                    (invited_by or "").strip() or None,
                ),
            )
            row = cursor.fetchone()
        conn.commit()
        return {
            "email": row[0],
            "name": row[1],
            "role": row[2],
            "business_id": row[3],
            "assigned_intents": row[4] or [],
            "status": row[5],
        }
    except DatabaseError as exc:
        conn.rollback()
        logger.error("Failed invite_user(email=%s): %s", normalized_email, exc)
        raise
    finally:
        conn.close()


def get_app_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Lookup app user by email."""
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return None

    conn = get_connection()
    if conn is None:
        logger.warning("DB unavailable in get_app_user_by_email(email=%s)", normalized_email)
        return None

    query = """
    SELECT email, name, role, business_id, assigned_intents, status, firebase_uid
    FROM app_users
    WHERE email = %s
    LIMIT 1
    """

    try:
        _create_app_users_table_if_not_exists(conn)
        with conn.cursor() as cursor:
            cursor.execute(query, (normalized_email,))
            row = cursor.fetchone()
        if not row:
            return None
        return {
            "email": row[0],
            "name": row[1],
            "role": row[2],
            "business_id": row[3],
            "assigned_intents": row[4] or [],
            "status": row[5],
            "firebase_uid": row[6],
        }
    except DatabaseError as exc:
        logger.error("Failed get_app_user_by_email(email=%s): %s", normalized_email, exc)
        return None
    finally:
        conn.close()


def activate_app_user(*, email: str, firebase_uid: str) -> Optional[Dict[str, Any]]:
    """Activate a previously invited user after Firebase signup completes."""
    normalized_email = (email or "").strip().lower()
    if not normalized_email:
        return None

    conn = get_connection()
    if conn is None:
        logger.warning("DB unavailable in activate_app_user(email=%s)", normalized_email)
        return None

    query = """
    UPDATE app_users
    SET status = 'active',
        firebase_uid = %s,
        activated_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE email = %s
      AND status IN ('invited', 'active')
    RETURNING email, name, role, business_id, assigned_intents, status, firebase_uid
    """

    try:
        _create_app_users_table_if_not_exists(conn)
        with conn.cursor() as cursor:
            cursor.execute(query, ((firebase_uid or "").strip() or None, normalized_email))
            row = cursor.fetchone()
        conn.commit()
        if not row:
            return None
        return {
            "email": row[0],
            "name": row[1],
            "role": row[2],
            "business_id": row[3],
            "assigned_intents": row[4] or [],
            "status": row[5],
            "firebase_uid": row[6],
        }
    except DatabaseError as exc:
        conn.rollback()
        logger.error("Failed activate_app_user(email=%s): %s", normalized_email, exc)
        return None
    finally:
        conn.close()

