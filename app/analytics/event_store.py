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
    "report_queued",
    "report_cache_redownload_completed",
    "report_cache_redownload_failed",
    "excel_export_completed",
    "excel_download_completed",
    "excel_download_failed",
    "query_submitted",
    "results_viewed",
    "exclusion_row_opened",
    "second_query_attempted",
    "paywall_shown",
    "bundle_purchased",
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

    def ab_conversion_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Computes key pricing & A/B testing conversion metrics broken down by variant:
        - Time from first query to first exclusion row opened (aha moment proxy)
        - Free to second-query-attempt rate
        - Paywall to purchase rate
        - Purchase rate broken out by whether the user opened an excluded source during free query
        - Free query abandonment rate (submitted but never viewed)
        - Side by side Variant A vs Variant B metrics
        """
        days = min(max(int(days), 1), 365)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_name, user_key, session_id, occurred_at, properties_json
                FROM analytics_events
                WHERE occurred_at >= datetime('now', ?)
                ORDER BY occurred_at ASC
                """,
                (f"-{days} days",),
            ).fetchall()

        events = []
        for r in rows:
            try:
                props = json.loads(r["properties_json"]) if r["properties_json"] else {}
            except Exception:
                props = {}
            events.append({
                "event_name": r["event_name"],
                "user_key": r["user_key"],
                "session_id": r["session_id"],
                "occurred_at": r["occurred_at"],
                "properties": props,
            })

        # Group data by variant: overall, variant_a, variant_b
        def compute_group_metrics(group_events: List[Dict[str, Any]]) -> Dict[str, Any]:
            users = set()
            first_query_time = {}  # user_key -> iso
            first_exclusion_time = {}  # user_key -> iso
            free_query_users = set()
            second_query_attempted_users = set()
            paywall_shown_users = set()
            purchased_users = set()
            opened_exclusion_users = set()
            submitted_runs = set()  # run_id
            viewed_runs = set()  # run_id

            for ev in group_events:
                name = ev["event_name"]
                uk = ev["user_key"]
                props = ev["properties"]
                ts = ev["occurred_at"]
                run_id = props.get("run_id")
                tier = props.get("tier")

                users.add(uk)

                if name == "query_submitted":
                    if uk not in first_query_time:
                        first_query_time[uk] = ts
                    if tier == "free":
                        free_query_users.add(uk)
                    if run_id:
                        submitted_runs.add(str(run_id))

                elif name == "results_viewed":
                    if run_id:
                        viewed_runs.add(str(run_id))

                elif name == "exclusion_row_opened":
                    if uk not in first_exclusion_time:
                        first_exclusion_time[uk] = ts
                    if props.get("is_excluded_row", True):
                        opened_exclusion_users.add(uk)

                elif name == "second_query_attempted":
                    second_query_attempted_users.add(uk)

                elif name == "paywall_shown":
                    paywall_shown_users.add(uk)

                elif name == "bundle_purchased":
                    purchased_users.add(uk)

            # 1. Time from first query to first exclusion row opened
            time_to_aha_seconds = []
            for uk, fq_ts in first_query_time.items():
                if uk in first_exclusion_time:
                    try:
                        t1 = datetime.fromisoformat(fq_ts.replace("Z", "+00:00")).timestamp()
                        t2 = datetime.fromisoformat(first_exclusion_time[uk].replace("Z", "+00:00")).timestamp()
                        diff = max(0.0, t2 - t1)
                        time_to_aha_seconds.append(diff)
                    except Exception:
                        pass
            avg_time_to_aha = round(sum(time_to_aha_seconds) / len(time_to_aha_seconds), 2) if time_to_aha_seconds else 0.0

            # 2. Free to second-query-attempt rate
            free_user_count = len(free_query_users)
            second_query_count = len(second_query_attempted_users)
            free_to_second_rate = round(second_query_count / free_user_count, 4) if free_user_count > 0 else 0.0

            # 3. Paywall to purchase rate
            paywall_count = len(paywall_shown_users)
            purchase_count = len(purchased_users)
            paywall_to_purchase_rate = round(purchase_count / paywall_count, 4) if paywall_count > 0 else 0.0

            # 4. Purchase rate broken out by whether user opened an excluded source during free query
            opened_and_purchased = len(opened_exclusion_users.intersection(purchased_users))
            opened_total = len(opened_exclusion_users)
            purchase_rate_opened_exclusion = round(opened_and_purchased / opened_total, 4) if opened_total > 0 else 0.0

            did_not_open_users = free_query_users - opened_exclusion_users
            did_not_open_purchased = len(did_not_open_users.intersection(purchased_users))
            did_not_open_total = len(did_not_open_users)
            purchase_rate_unopened_exclusion = round(did_not_open_purchased / did_not_open_total, 4) if did_not_open_total > 0 else 0.0

            # 5. Free query abandonment rate (submitted but never viewed)
            total_free_submitted = len(submitted_runs)
            abandoned_runs = len(submitted_runs - viewed_runs)
            free_query_abandonment_rate = round(abandoned_runs / total_free_submitted, 4) if total_free_submitted > 0 else 0.0

            # Exclusion row opened rate (users who opened / free query users)
            exclusion_row_opened_rate = round(opened_total / free_user_count, 4) if free_user_count > 0 else 0.0

            return {
                "unique_users": len(users),
                "free_query_users": free_user_count,
                "second_query_attempted_users": second_query_count,
                "paywall_shown_users": paywall_count,
                "purchased_users": purchase_count,
                "opened_exclusion_users": opened_total,
                "avg_time_to_first_exclusion_seconds": avg_time_to_aha,
                "free_to_second_query_rate": free_to_second_rate,
                "paywall_to_purchase_rate": paywall_to_purchase_rate,
                "exclusion_row_opened_rate": exclusion_row_opened_rate,
                "purchase_rate_opened_exclusion": purchase_rate_opened_exclusion,
                "purchase_rate_unopened_exclusion": purchase_rate_unopened_exclusion,
                "free_query_abandonment_rate": free_query_abandonment_rate,
            }

        variant_a_events = [ev for ev in events if ev["properties"].get("variant") == "variant_a"]
        variant_b_events = [ev for ev in events if ev["properties"].get("variant") == "variant_b"]

        return {
            "window_days": days,
            "overall": compute_group_metrics(events),
            "variant_a": compute_group_metrics(variant_a_events),
            "variant_b": compute_group_metrics(variant_b_events),
        }
