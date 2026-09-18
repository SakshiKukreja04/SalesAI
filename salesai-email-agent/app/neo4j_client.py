"""Optional shared Neo4j driver for graph-backed SalesAI context."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from dotenv import load_dotenv

load_dotenv()

LOGGER = logging.getLogger(__name__)


class Neo4jClient:
    """Own one process-wide Neo4j driver and expose safe connectivity helpers."""

    def __init__(self) -> None:
        self.uri = os.getenv("NEO4J_URI", "").strip()
        self.username = os.getenv("NEO4J_USERNAME", "").strip()
        self.password = os.getenv("NEO4J_PASSWORD", "")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j").strip() or "neo4j"
        self._driver: Any = None
        self._lock = threading.Lock()

        if not all((self.uri, self.username, self.password)):
            LOGGER.info("Neo4j is not configured; graph retrieval will be skipped")
            return

        try:
            self._create_driver()
            LOGGER.info("Neo4j driver initialized")
        except Exception as exc:
            LOGGER.warning("Neo4j driver initialization failed: %s", exc)

    def _create_driver(self) -> None:
        from neo4j import GraphDatabase

        self._driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
            connection_timeout=5.0,
            max_connection_lifetime=120.0,
            max_transaction_retry_time=5.0,
            liveness_check_timeout=2.0,
            keep_alive=True,
        )

    @property
    def configured(self) -> bool:
        return self._driver is not None

    def verify_connectivity(self) -> bool:
        """Verify connectivity without logging credentials or customer data."""
        if not self._driver:
            return False
        try:
            self._driver.verify_connectivity()
            LOGGER.info("Neo4j connectivity verified")
            return True
        except Exception as exc:
            LOGGER.warning("Neo4j connectivity check failed: %s", exc)
            return False

    def session(self) -> Any:
        """Create a database-scoped session for callers that need one."""
        if not self._driver:
            raise RuntimeError("Neo4j is not configured")
        if self.database and self.database not in {"neo4j", "default"}:
            return self._driver.session(database=self.database)
        return self._driver.session()

    def read_records(self, query: str, **params: Any) -> list[dict[str, Any]]:
        """Run a read query and recreate a defunct driver once if needed."""
        if not self._driver:
            return []

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                with self.session() as session:
                    return [dict(record) for record in session.run(query, **params)]
            except Exception as exc:
                last_error = exc
                if attempt == 0 and self._is_connection_error(exc):
                    LOGGER.warning("Neo4j read connection reset; reconnecting once")
                    with self._lock:
                        if self._driver:
                            self._driver.close()
                        self._create_driver()
                    continue
                raise

        if last_error:
            raise last_error
        return []

    @staticmethod
    def _is_connection_error(error: Exception) -> bool:
        name = type(error).__name__
        return name in {
            "ConnectionResetError",
            "SessionExpired",
            "ServiceUnavailable",
            "TransientError",
            "WriteServiceUnavailable",
        } or "defunct connection" in str(error).lower()

    def close(self) -> None:
        with self._lock:
            if self._driver:
                self._driver.close()
                self._driver = None
                LOGGER.info("Neo4j driver closed")


neo4j_client = Neo4jClient()