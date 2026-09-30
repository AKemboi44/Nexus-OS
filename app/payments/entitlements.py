import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class EntitlementStore:
    """Durable server-side subscription state used to authorize paid features."""

    def __init__(self, database_path: str = None):
        self.database_path = database_path or os.getenv(
            "NEXUS_ENTITLEMENTS_DB",
            os.path.join(os.getcwd(), "nexus_entitlements.sqlite3"),
        )
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entitlements (
                    user_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    plan TEXT,
                    status TEXT NOT NULL,
                    starts_at TEXT,
                    ends_at TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_entitlements_provider "
                "ON entitlements(provider, provider_id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_events (
                    event_id TEXT PRIMARY KEY,
                    received_at TEXT NOT NULL
                )
                """
            )

    def upsert(
        self,
        user_key: str,
        provider: str,
        provider_id: str,
        status: str,
        plan: Optional[str] = None,
        starts_at: Optional[str] = None,
        ends_at: Optional[str] = None,
    ):
        if not user_key or not provider_id:
            raise ValueError("user_key and provider_id are required.")
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO entitlements
                (user_key, provider, provider_id, plan, status, starts_at, ends_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_key) DO UPDATE SET
                    provider=excluded.provider,
                    provider_id=excluded.provider_id,
                    plan=excluded.plan,
                    status=excluded.status,
                    starts_at=excluded.starts_at,
                    ends_at=excluded.ends_at,
                    updated_at=excluded.updated_at
                """,
                (
                    user_key,
                    provider,
                    provider_id,
                    plan,
                    status,
                    starts_at,
                    ends_at,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def get(self, user_key: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM entitlements WHERE user_key = ?", (user_key,)
            ).fetchone()
        return dict(row) if row else None

    def get_by_provider(self, provider: str, provider_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM entitlements WHERE provider = ? AND provider_id = ?",
                (provider, provider_id),
            ).fetchone()
        return dict(row) if row else None

    def is_active(self, user_key: str) -> bool:
        record = self.get(user_key)
        return bool(record and record["status"] in {"ACTIVE", "APPROVED", "COMPLETED"})

    def claim_event(self, event_id: str) -> bool:
        """Return False for a replayed webhook event."""
        if not event_id:
            raise ValueError("event_id is required.")
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO payment_events(event_id, received_at) VALUES (?, ?)",
                (event_id, datetime.now(timezone.utc).isoformat()),
            )
            return cursor.rowcount == 1
