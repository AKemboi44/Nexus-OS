import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.supabase_store import SupabaseRestClient


OPERATIONAL_EVENT_NAMES = (
    "scan_completed",
    "scan_failed",
    "report_completed",
    "report_failed",
    "report_cache_redownload_completed",
    "report_cache_redownload_failed",
    "excel_export_completed",
    "excel_download_completed",
    "excel_download_failed",
)


class AnalyticsEventStore:
    """Small durable event store for funnel, error, and product-usage analytics."""

    def __init__(self, database_path: str = None):
        self.supabase = SupabaseRestClient.from_env()
        if self.supabase:
            return
        self.database_path = database_path or os.getenv(
            "NEXUS_ANALYTICS_DB",
            os.path.join(os.getcwd(), "nexus_analytics.sqlite3"),
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
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    user_key TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    properties_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_name_time "
                "ON analytics_events(event_name, occurred_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_user_time "
                "ON analytics_events(user_key, occurred_at)"
            )

    @staticmethod
    def _user_key(user_id: str) -> str:
        value = str(user_id or "anonymous").strip().lower()
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]

    def record(
        self,
        event_name: str,
        user_id: str = "anonymous",
        session_id: str = "unknown",
        properties: Dict[str, Any] = None,
        occurred_at: str = None,
    ):
        if not event_name or len(event_name) > 120:
            raise ValueError("event_name must be between 1 and 120 characters.")
        payload = properties or {}
        if not isinstance(payload, dict):
            raise ValueError("properties must be an object.")
        timestamp = occurred_at or datetime.now(timezone.utc).isoformat()
        if self.supabase:
            self.supabase.insert(
                "analytics_events",
                {
                    "event_name": event_name,
                    "user_id": user_id if user_id != "anonymous" else None,
                    "session_id": str(session_id or "unknown")[:120],
                    "occurred_at": timestamp,
                    "properties": payload,
                },
            )
            return
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analytics_events
                (event_name, user_key, session_id, occurred_at, properties_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_name,
                    self._user_key(user_id),
                    str(session_id or "unknown")[:120],
                    timestamp,
                    json.dumps(payload, ensure_ascii=False, default=str)[:10000],
                ),
            )

    def summary(self, days: int = 30) -> Dict[str, Any]:
        days = min(max(int(days), 1), 365)
        if self.supabase:
            result = self.supabase.request(
                "POST",
                "rpc/nexus_analytics_summary",
                json={"days": days},
            )
            if not isinstance(result, dict):
                raise RuntimeError("Supabase returned an invalid analytics summary.")
            return result
        with self._connect() as connection:
            totals = connection.execute(
                """
                SELECT event_name, COUNT(*) AS event_count,
                       COUNT(DISTINCT user_key) AS unique_users
                FROM analytics_events
                WHERE occurred_at >= datetime('now', ?)
                GROUP BY event_name
                ORDER BY event_count DESC
                """,
                (f"-{days} days",),
            ).fetchall()
            errors = connection.execute(
                """
                SELECT json_extract(properties_json, '$.error_code') AS error_code,
                       json_extract(properties_json, '$.message') AS message,
                       COUNT(*) AS occurrences
                FROM analytics_events
                WHERE event_name IN ('error', 'scan_failed', 'report_failed', 'payment_failed')
                  AND occurred_at >= datetime('now', ?)
                GROUP BY error_code, message
                ORDER BY occurrences DESC
                LIMIT 25
                """,
                (f"-{days} days",),
            ).fetchall()
            operational = connection.execute(
                """
                SELECT event_name,
                       COUNT(*) AS event_count,
                       SUM(CASE WHEN json_extract(properties_json, '$.duration_ms') IS NOT NULL
                                THEN 1 ELSE 0 END) AS timed_events,
                       ROUND(AVG(CAST(json_extract(properties_json, '$.duration_ms') AS REAL))) AS average_duration_ms,
                       SUM(CASE WHEN json_extract(properties_json, '$.cache_hit') = 1
                                THEN 1 ELSE 0 END) AS cache_hits
                FROM analytics_events
                WHERE event_name IN ({})
                  AND occurred_at >= datetime('now', ?)
                GROUP BY event_name
                ORDER BY event_count DESC
                """.format(",".join("?" for _ in OPERATIONAL_EVENT_NAMES)),
                (*OPERATIONAL_EVENT_NAMES, f"-{days} days"),
            ).fetchall()

        return {
            "window_days": days,
            "events": [dict(row) for row in totals],
            "common_errors": [dict(row) for row in errors],
            "funnel": self._funnel(days),
            "operational_metrics": [dict(row) for row in operational],
        }

    def _funnel(self, days: int) -> List[Dict[str, Any]]:
        stages = [
            ("workspace_opened", "Workspace opened"),
            ("scan_started", "Research scan started"),
            ("scan_completed", "Research scan completed"),
            ("report_started", "Report generation started"),
            ("report_completed", "Report generated"),
            ("checkout_started", "Checkout started"),
            ("payment_completed", "Payment completed"),
        ]
        with self._connect() as connection:
            result = []
            for event_name, label in stages:
                row = connection.execute(
                    """
                    SELECT COUNT(DISTINCT user_key) AS users, COUNT(*) AS events
                    FROM analytics_events
                    WHERE event_name = ? AND occurred_at >= datetime('now', ?)
                    """,
                    (event_name, f"-{days} days"),
                ).fetchone()
                result.append(
                    {
                        "stage": event_name,
                        "label": label,
                        "unique_users": row["users"],
                        "events": row["events"],
                    }
                )
            return result
