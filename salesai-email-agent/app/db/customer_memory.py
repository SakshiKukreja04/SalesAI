"""Database access layer for Customer Memory (Supabase / PostgreSQL).

Handles customers, customer_issues, customer_interests, and conversations tables.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Union

from app.db.supabase_client import get_connection
from app.memory.memory_models import (
    ConversationRecord,
    CustomerInterest,
    CustomerIssue,
    CustomerProfile,
)

LOGGER = logging.getLogger(__name__)


def normalize_email(email: str) -> str:
    """Normalize customer email for deterministic identity resolution.
    
    Handles:
    - Uppercase / lowercase normalization
    - Leading/trailing whitespace
    - Display names (e.g. 'John Doe <john@example.com>' -> 'john@example.com')
    """
    if not email:
        return ""
    
    clean = email.strip()
    match = re.search(r"<([^>]+)>", clean)
    if match:
        clean = match.group(1).strip()
    
    return clean.lower()


def ensure_memory_tables_exist() -> None:
    """Ensure customers, customer_issues, customer_interests, and conversations exist."""
    conn = get_connection()
    if conn is None:
        LOGGER.warning("DB unavailable in ensure_memory_tables_exist")
        return

    queries = [
        """
        CREATE TABLE IF NOT EXISTS customers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT UNIQUE NOT NULL,
            normalized_email TEXT,
            name TEXT DEFAULT '',
            business_id TEXT DEFAULT '',
            total_interactions INT DEFAULT 0,
            first_contact_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_contact_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_customers_email ON customers (email);
        CREATE INDEX IF NOT EXISTS idx_customers_normalized_email ON customers (normalized_email);
        """,
        """
        CREATE TABLE IF NOT EXISTS customer_issues (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID NOT NULL,
            issue_title TEXT NOT NULL,
            issue_description TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'medium',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_customer_issues_customer_id ON customer_issues (customer_id);
        CREATE INDEX IF NOT EXISTS idx_customer_issues_status ON customer_issues (status);
        """,
        """
        CREATE TABLE IF NOT EXISTS customer_interests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID NOT NULL,
            product_name TEXT NOT NULL,
            interest_status TEXT DEFAULT 'active',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_customer_interests_customer_id ON customer_interests (customer_id);
        """,
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID NOT NULL,
            email_id TEXT UNIQUE,
            subject TEXT DEFAULT '',
            customer_message TEXT DEFAULT '',
            normalized_message TEXT DEFAULT '',
            intent TEXT DEFAULT 'general_support',
            intent_confidence DOUBLE PRECISION DEFAULT 0.5,
            emotion TEXT DEFAULT 'neutral',
            emotion_confidence DOUBLE PRECISION DEFAULT 0.5,
            strategy TEXT DEFAULT 'general_helpful',
            generated_reply TEXT DEFAULT '',
            confidence DOUBLE PRECISION DEFAULT 0.5,
            status TEXT DEFAULT 'replied',
            escalation_reason TEXT DEFAULT '',
            selected_model TEXT DEFAULT 'gemini',
            retrieved_context_count INT DEFAULT 0,
            similar_memory_count INT DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_conversations_customer_id ON conversations (customer_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_email_id ON conversations (email_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations (created_at DESC);
        """,
    ]

    try:
        with conn.cursor() as cursor:
            for q in queries:
                cursor.execute(q)
        conn.commit()
        LOGGER.info("Memory schema tables ensured (customers, issues, interests, conversations)")
    except Exception as exc:
        conn.rollback()
        LOGGER.error("Failed to ensure memory tables: %s", exc)
    finally:
        conn.close()


def resolve_or_create_customer(email: str, name: str = "") -> CustomerProfile:
    """Resolve customer by normalized email.
    
    1. Normalizes email.
    2. Searches customers table by normalized_email or email.
    3. If exists: updates last_contact_at and increments total_interactions.
    4. If not exists: creates new customer record.
    """
    clean_email = normalize_email(email)
    if not clean_email:
        return CustomerProfile(customer_id="0", email="anonymous@unknown.com", name=name or "Valued Customer")

    conn = get_connection()
    if conn is None:
        LOGGER.warning("DB unavailable in resolve_or_create_customer, using in-memory profile")
        return CustomerProfile(customer_id="0", email=clean_email, name=name or "Valued Customer", total_interactions=1)

    now = datetime.now(timezone.utc)
    clean_name = (name or "").strip()

    try:
        ensure_memory_tables_exist()
        with conn.cursor() as cursor:
            # 1. Look up existing
            cursor.execute(
                """
                SELECT id, email, name, total_interactions, first_contact_at, last_contact_at, created_at, updated_at
                FROM customers
                WHERE email = %s OR normalized_email = %s
                LIMIT 1
                """,
                (clean_email, clean_email),
            )
            row = cursor.fetchone()

            if row:
                customer_id = row[0]
                existing_name = row[2] or ""
                total_interactions = (row[3] or 0) + 1
                first_contact_at = row[4]

                updated_name = clean_name if (clean_name and not existing_name) else existing_name

                cursor.execute(
                    """
                    UPDATE customers
                    SET total_interactions = %s,
                        name = %s,
                        last_contact_at = %s,
                        updated_at = %s,
                        normalized_email = %s
                    WHERE id::text = %s::text
                    """,
                    (total_interactions, updated_name, now, now, clean_email, str(customer_id)),
                )
                conn.commit()
                LOGGER.info("Resolved existing customer id=%s email=%s total_interactions=%d", customer_id, clean_email, total_interactions)
                return CustomerProfile(
                    customer_id=customer_id,
                    email=clean_email,
                    name=updated_name,
                    total_interactions=total_interactions,
                    first_contact_at=first_contact_at,
                    last_contact_at=now,
                )

            # 2. Insert new customer
            cursor.execute(
                """
                INSERT INTO customers (email, normalized_email, name, total_interactions, first_contact_at, last_contact_at, created_at, updated_at)
                VALUES (%s, %s, %s, 1, %s, %s, %s, %s)
                RETURNING id
                """,
                (clean_email, clean_email, clean_name, now, now, now, now),
            )
            new_id = cursor.fetchone()[0]
            conn.commit()
            LOGGER.info("Created new customer id=%s email=%s name=%s", new_id, clean_email, clean_name)
            return CustomerProfile(
                customer_id=new_id,
                email=clean_email,
                name=clean_name,
                total_interactions=1,
                first_contact_at=now,
                last_contact_at=now,
            )

    except Exception as exc:
        conn.rollback()
        LOGGER.error("Failed resolve_or_create_customer for %s: %s", clean_email, exc)
        return CustomerProfile(customer_id="0", email=clean_email, name=clean_name, total_interactions=1)
    finally:
        conn.close()


def update_customer_name(customer_id: Union[str, int], name: str) -> bool:
    """Update customer name if reliably discovered."""
    clean_name = (name or "").strip()
    if not clean_name or not customer_id or str(customer_id) in {"0", ""}:
        return False

    conn = get_connection()
    if conn is None:
        return False

    now = datetime.now(timezone.utc)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE customers
                SET name = %s,
                    updated_at = %s
                WHERE id::text = %s::text AND (name IS NULL OR name = '' OR name = 'Valued Customer')
                """,
                (clean_name, now, str(customer_id)),
            )
            conn.commit()
            return True
    except Exception as exc:
        conn.rollback()
        LOGGER.error("Failed update_customer_name(%s, %s): %s", customer_id, clean_name, exc)
        return False
    finally:
        conn.close()


def get_customer_by_id(customer_id: Union[str, int]) -> Optional[CustomerProfile]:
    """Fetch customer profile by customer_id."""
    if not customer_id or str(customer_id) in {"0", ""}:
        return None

    conn = get_connection()
    if conn is None:
        return None

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, email, name, total_interactions, first_contact_at, last_contact_at, created_at, updated_at
                FROM customers
                WHERE id::text = %s::text
                LIMIT 1
                """,
                (str(customer_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return CustomerProfile(
                customer_id=row[0],
                email=row[1],
                name=row[2] or "",
                total_interactions=row[3] or 0,
                first_contact_at=row[4],
                last_contact_at=row[5],
                created_at=row[6],
                updated_at=row[7],
            )
    except Exception as exc:
        LOGGER.error("Failed get_customer_by_id(%s): %s", customer_id, exc)
        return None
    finally:
        conn.close()


def get_customer_conversations(customer_id: Union[str, int], limit: int = 10) -> List[ConversationRecord]:
    """Fetch recent conversations for a customer in reverse chronological order."""
    if not customer_id or str(customer_id) in {"0", ""}:
        return []

    conn = get_connection()
    if conn is None:
        return []

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, customer_id, email_id, subject, customer_message, normalized_message,
                       intent, intent_confidence, emotion, emotion_confidence, strategy,
                       generated_reply, confidence, status, escalation_reason, selected_model,
                       retrieved_context_count, similar_memory_count, created_at, updated_at
                FROM conversations
                WHERE customer_id::text = %s::text
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (str(customer_id), limit),
            )
            rows = cursor.fetchall()
            conversations = []
            for r in rows:
                conversations.append(
                    ConversationRecord(
                        id=r[0],
                        customer_id=r[1],
                        email_id=r[2] or "",
                        subject=r[3] or "",
                        customer_message=r[4] or "",
                        normalized_message=r[5] or "",
                        intent=r[6] or "general_support",
                        intent_confidence=float(r[7] or 0.5),
                        emotion=r[8] or "neutral",
                        emotion_confidence=float(r[9] or 0.5),
                        strategy=r[10] or "general_helpful",
                        generated_reply=r[11] or "",
                        confidence=float(r[12] or 0.5),
                        status=r[13] or "replied",
                        escalation_reason=r[14] or "",
                        selected_model=r[15] or "gemini",
                        retrieved_context_count=int(r[16] or 0),
                        similar_memory_count=int(r[17] or 0),
                        created_at=r[18],
                        updated_at=r[19],
                    )
                )
            return conversations
    except Exception as exc:
        LOGGER.error("Failed get_customer_conversations(customer_id=%s): %s", customer_id, exc)
        return []
    finally:
        conn.close()


def get_customer_issues(customer_id: Union[str, int], status: Optional[str] = None) -> List[CustomerIssue]:
    """Fetch customer issues filtered by status ('open', 'resolved', 'escalated' or None for all)."""
    if not customer_id or str(customer_id) in {"0", ""}:
        return []

    conn = get_connection()
    if conn is None:
        return []

    try:
        with conn.cursor() as cursor:
            if status:
                cursor.execute(
                    """
                    SELECT id, customer_id, issue_title, issue_description, status, priority, created_at, updated_at
                    FROM customer_issues
                    WHERE customer_id::text = %s::text AND status = %s
                    ORDER BY updated_at DESC
                    """,
                    (str(customer_id), status),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, customer_id, issue_title, issue_description, status, priority, created_at, updated_at
                    FROM customer_issues
                    WHERE customer_id::text = %s::text
                    ORDER BY updated_at DESC
                    """,
                    (str(customer_id),),
                )
            rows = cursor.fetchall()
            issues = []
            for r in rows:
                issues.append(
                    CustomerIssue(
                        id=r[0],
                        customer_id=r[1],
                        issue_title=r[2] or "",
                        description=r[3] or "",
                        status=r[4] or "open",
                        priority=r[5] or "medium",
                        resolution_notes="",
                        created_at=r[6],
                        updated_at=r[7],
                    )
                )
            return issues
    except Exception as exc:
        LOGGER.error("Failed get_customer_issues(customer_id=%s): %s", customer_id, exc)
        return []
    finally:
        conn.close()


def create_or_update_customer_issue(
    customer_id: Union[str, int],
    issue_title: str,
    description: str = "",
    status: str = "open",
    priority: str = "medium",
    resolution_notes: str = "",
) -> Optional[Union[str, int]]:
    """Create a new customer issue or update an existing one deterministically."""
    if not customer_id or not issue_title or str(customer_id) in {"0", ""}:
        return None

    conn = get_connection()
    if conn is None:
        return None

    now = datetime.now(timezone.utc)
    clean_title = issue_title.strip()

    try:
        ensure_memory_tables_exist()
        with conn.cursor() as cursor:
            # Check for existing issue with matching or similar title for this customer
            cursor.execute(
                """
                SELECT id, status
                FROM customer_issues
                WHERE customer_id::text = %s::text AND (LOWER(issue_title) = LOWER(%s) OR (status = 'open' AND LOWER(issue_title) LIKE %s))
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (str(customer_id), clean_title, f"%{clean_title[:15].lower()}%"),
            )
            row = cursor.fetchone()

            if row:
                issue_id = row[0]
                cursor.execute(
                    """
                    UPDATE customer_issues
                    SET status = %s,
                        priority = %s,
                        issue_description = COALESCE(NULLIF(%s, ''), issue_description),
                        updated_at = %s
                    WHERE id::text = %s::text
                    """,
                    (status, priority, description.strip(), now, str(issue_id)),
                )
                conn.commit()
                LOGGER.info("Updated customer issue id=%s status=%s", issue_id, status)
                return issue_id

            # Insert new issue
            cursor.execute(
                """
                INSERT INTO customer_issues (customer_id, issue_title, issue_description, status, priority, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (str(customer_id), clean_title, description.strip(), status, priority, now, now),
            )
            new_id = cursor.fetchone()[0]
            conn.commit()
            LOGGER.info("Created customer issue id=%s title=%s for customer_id=%s", new_id, clean_title, customer_id)
            return new_id

    except Exception as exc:
        conn.rollback()
        LOGGER.error("Failed create_or_update_customer_issue: %s", exc)
        return None
    finally:
        conn.close()


def get_customer_interests(customer_id: Union[str, int], status: str = "active") -> List[CustomerInterest]:
    """Fetch tracked product interests for a customer."""
    if not customer_id or str(customer_id) in {"0", ""}:
        return []

    conn = get_connection()
    if conn is None:
        return []

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, customer_id, product_name, interest_status, created_at, updated_at
                FROM customer_interests
                WHERE customer_id::text = %s::text AND (interest_status = %s OR %s IS NULL)
                ORDER BY updated_at DESC
                """,
                (str(customer_id), status, status),
            )
            rows = cursor.fetchall()
            interests = []
            for r in rows:
                interests.append(
                    CustomerInterest(
                        id=r[0],
                        customer_id=r[1],
                        product_name=r[2] or "",
                        interest_status=r[3] or "active",
                        created_at=r[4],
                        updated_at=r[5],
                    )
                )
            return interests
    except Exception as exc:
        LOGGER.error("Failed get_customer_interests(customer_id=%s): %s", customer_id, exc)
        return []
    finally:
        conn.close()


def create_or_update_customer_interest(
    customer_id: Union[str, int],
    product_name: str,
    status: str = "active",
) -> bool:
    """Record customer product interest with deterministic deduplication."""
    if not customer_id or not product_name or str(customer_id) in {"0", ""}:
        return False

    clean_product = product_name.strip()
    conn = get_connection()
    if conn is None:
        return False

    now = datetime.now(timezone.utc)

    try:
        ensure_memory_tables_exist()
        with conn.cursor() as cursor:
            # Check for existing interest on this product
            cursor.execute(
                """
                SELECT id FROM customer_interests
                WHERE customer_id::text = %s::text AND LOWER(product_name) = LOWER(%s)
                LIMIT 1
                """,
                (str(customer_id), clean_product),
            )
            row = cursor.fetchone()

            if row:
                cursor.execute(
                    """
                    UPDATE customer_interests
                    SET interest_status = %s,
                        updated_at = %s
                    WHERE id::text = %s::text
                    """,
                    (status, now, str(row[0])),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO customer_interests (customer_id, product_name, interest_status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (str(customer_id), clean_product, status, now, now),
                )
            conn.commit()
            LOGGER.info("Recorded product interest '%s' (status=%s) for customer_id=%s", clean_product, status, customer_id)
            return True
    except Exception as exc:
        conn.rollback()
        LOGGER.error("Failed create_or_update_customer_interest: %s", exc)
        return False
    finally:
        conn.close()


def save_conversation_record(record: Dict[str, Any]) -> bool:
    """Persist conversation record with email_id idempotency protection."""
    customer_id = record.get("customer_id", 0)
    email_id = record.get("email_id") or ""

    if not customer_id or str(customer_id) in {"0", ""}:
        return False

    conn = get_connection()
    if conn is None:
        LOGGER.warning("DB unavailable for save_conversation_record")
        return False

    now = datetime.now(timezone.utc)

    try:
        ensure_memory_tables_exist()
        with conn.cursor() as cursor:
            if email_id:
                # Idempotency check
                cursor.execute(
                    """
                    SELECT id FROM conversations
                    WHERE email_id = %s
                    LIMIT 1
                    """,
                    (email_id,),
                )
                existing = cursor.fetchone()
                if existing:
                    cursor.execute(
                        """
                        UPDATE conversations
                        SET subject = %s,
                            customer_message = %s,
                            normalized_message = %s,
                            intent = %s,
                            intent_confidence = %s,
                            emotion = %s,
                            emotion_confidence = %s,
                            strategy = %s,
                            generated_reply = %s,
                            confidence = %s,
                            status = %s,
                            escalation_reason = %s,
                            selected_model = %s,
                            retrieved_context_count = %s,
                            similar_memory_count = %s,
                            updated_at = %s
                        WHERE id::text = %s::text
                        """,
                        (
                            record.get("subject", ""),
                            record.get("customer_message", ""),
                            record.get("normalized_message", ""),
                            record.get("intent", "general_support"),
                            float(record.get("intent_confidence", 0.5)),
                            record.get("emotion", "neutral"),
                            float(record.get("emotion_confidence", 0.5)),
                            record.get("strategy", "general_helpful"),
                            record.get("generated_reply", ""),
                            float(record.get("confidence", 0.5)),
                            record.get("status", "replied"),
                            record.get("escalation_reason", ""),
                            record.get("selected_model", "gemini"),
                            int(record.get("retrieved_context_count", 0)),
                            int(record.get("similar_memory_count", 0)),
                            now,
                            str(existing[0]),
                        ),
                    )
                    conn.commit()
                    LOGGER.info("Updated existing conversation email_id=%s (id=%s)", email_id, existing[0])
                    return True

            # Insert new conversation
            cursor.execute(
                """
                INSERT INTO conversations (
                    customer_id, email_id, subject, customer_message, normalized_message,
                    intent, intent_confidence, emotion, emotion_confidence, strategy,
                    generated_reply, confidence, status, escalation_reason, selected_model,
                    retrieved_context_count, similar_memory_count, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(customer_id),
                    email_id or None,
                    record.get("subject", ""),
                    record.get("customer_message", ""),
                    record.get("normalized_message", ""),
                    record.get("intent", "general_support"),
                    float(record.get("intent_confidence", 0.5)),
                    record.get("emotion", "neutral"),
                    float(record.get("emotion_confidence", 0.5)),
                    record.get("strategy", "general_helpful"),
                    record.get("generated_reply", ""),
                    float(record.get("confidence", 0.5)),
                    record.get("status", "replied"),
                    record.get("escalation_reason", ""),
                    record.get("selected_model", "gemini"),
                    int(record.get("retrieved_context_count", 0)),
                    int(record.get("similar_memory_count", 0)),
                    now,
                    now,
                ),
            )
            conn.commit()
            LOGGER.info("Saved conversation for customer_id=%s (email_id=%s)", customer_id, email_id)
            return True

    except Exception as exc:
        conn.rollback()
        LOGGER.error("Failed save_conversation_record: %s", exc)
        return False
    finally:
        conn.close()
