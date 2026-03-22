import logging
import os
from typing import Dict, Any, Optional

import psycopg2
from psycopg2 import DatabaseError, OperationalError
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_env() -> None:
    """Load environment variables from a .env file once."""
    if not getattr(_load_env, "loaded", False):
        load_dotenv()
        _load_env.loaded = True


def get_connection() -> Optional[psycopg2.extensions.connection]:
    """Create and return a PostgreSQL connection from SUPABASE_DB_URL."""
    _load_env()

    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        logger.error("SUPABASE_DB_URL is not set in environment variables")
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

    try:
        with conn.cursor() as cursor:
            cursor.execute(create_table_query)
        conn.commit()
        logger.info("Ensured customer_emails table exists")
    except DatabaseError:
        conn.rollback()
        logger.exception("Error while creating customer_emails table")
        raise
    finally:
        conn.close()
        logger.debug("PostgreSQL connection closed after create_table_if_not_exists")


def insert_email_data(email_data: Dict[str, Any]) -> None:
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
    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    values = (
        email_data.get("id"),
        email_data.get("from"),
        email_data.get("subject"),
        email_data.get("body"),
        email_data.get("intent"),
        email_data.get("emotion"),
        email_data.get("timestamp"),
    )

    try:
        with conn.cursor() as cursor:
            cursor.execute(insert_query, values)
        conn.commit()
        logger.info("Email data inserted into customer_emails table")
    except DatabaseError:
        conn.rollback()
        logger.exception("Failed to insert email data")
        raise
    finally:
        conn.close()
        logger.debug("PostgreSQL connection closed after insert_email_data")

