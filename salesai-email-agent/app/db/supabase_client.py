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

    try:
        with conn.cursor() as cursor:
            cursor.execute(create_table_query)
            cursor.execute(create_index_query)
        conn.commit()
        logger.info("Ensured customer_emails table and indexes exist")
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

