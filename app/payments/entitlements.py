import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from app.supabase_store import SupabaseRequestError, SupabaseRestClient
from app.payments.config import default_pricing_config, PricingConfig


class EntitlementStore:
    """Durable server-side subscription state used to authorize paid features."""

    def __init__(self, database_path: str = None):
        self.supabase = SupabaseRestClient.from_env()
        if self.supabase:
            return
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
                    updated_at TEXT NOT NULL,
                    bundle_queries_remaining INTEGER DEFAULT NULL,
                    total_queries_used INTEGER DEFAULT 0
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_query_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_key TEXT NOT NULL,
                    period_month TEXT NOT NULL,
                    query_count INTEGER DEFAULT 0,
                    last_queried_at TEXT NOT NULL,
                    UNIQUE(user_key, period_month)
                )
                """
            )
            # Add columns if migrating existing db
            try:
                connection.execute("ALTER TABLE entitlements ADD COLUMN bundle_queries_remaining INTEGER DEFAULT NULL")
            except Exception:
                pass
            try:
                connection.execute("ALTER TABLE entitlements ADD COLUMN total_queries_used INTEGER DEFAULT 0")
            except Exception:
                pass

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
        if self.supabase:
            self.supabase.request(
                "POST",
                "entitlements",
                params={"on_conflict": "user_id"},
                json={
                    "user_id": user_key,
                    "provider": provider,
                    "provider_id": provider_id,
                    "plan": plan,
                    "status": status,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                prefer="resolution=merge-duplicates,return=minimal",
            )
            return
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
        if self.supabase:
            rows = self.supabase.request(
                "GET",
                "entitlements",
                params={"user_id": f"eq.{user_key}", "select": "*", "limit": 1},
            )
            return rows[0] if rows else None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM entitlements WHERE user_key = ?", (user_key,)
            ).fetchone()
        return dict(row) if row else None

    def get_by_provider(self, provider: str, provider_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase:
            rows = self.supabase.request(
                "GET",
                "entitlements",
                params={
                    "provider": f"eq.{provider}",
                    "provider_id": f"eq.{provider_id}",
                    "select": "*",
                    "limit": 1,
                },
            )
            return rows[0] if rows else None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM entitlements WHERE provider = ? AND provider_id = ?",
                (provider, provider_id),
            ).fetchone()
        return dict(row) if row else None

    def is_active(self, user_key: str) -> bool:
        record = self.get(user_key)
        return bool(record and record["status"] in {"ACTIVE", "APPROVED", "COMPLETED"})

    @staticmethod
    def current_period_month() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def get_query_usage(self, user_key: str, period_month: Optional[str] = None) -> int:
        period = period_month or self.current_period_month()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT query_count FROM user_query_usage WHERE user_key = ? AND period_month = ?",
                (user_key, period),
            ).fetchone()
        return int(row["query_count"]) if row else 0

    def increment_query_usage(self, user_key: str, period_month: Optional[str] = None) -> int:
        period = period_month or self.current_period_month()
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_query_usage (user_key, period_month, query_count, last_queried_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_key, period_month) DO UPDATE SET
                    query_count = user_query_usage.query_count + 1,
                    last_queried_at = excluded.last_queried_at
                """,
                (user_key, period, now_iso),
            )
            # Also update bundle queries remaining if user has an active bundle
            entitlement = self.get(user_key)
            if entitlement and entitlement.get("bundle_queries_remaining") is not None:
                rem = max(0, int(entitlement["bundle_queries_remaining"]) - 1)
                tot = int(entitlement.get("total_queries_used") or 0) + 1
                connection.execute(
                    """
                    UPDATE entitlements
                    SET bundle_queries_remaining = ?, total_queries_used = ?, updated_at = ?
                    WHERE user_key = ?
                    """,
                    (rem, tot, now_iso, user_key),
                )
            row = connection.execute(
                "SELECT query_count FROM user_query_usage WHERE user_key = ? AND period_month = ?",
                (user_key, period),
            ).fetchone()
            return int(row["query_count"]) if row else 1

    def check_query_permission(
        self,
        user_key: str,
        config: Optional[PricingConfig] = None,
    ) -> Dict[str, Any]:
        """
        Determines whether the user can execute a research query under the current pricing config.
        Returns a dict:
        {
            "allowed": bool,
            "tier": "paid" | "free",
            "reason": str,
            "queries_used": int,
            "free_allowance": int,
            "queries_remaining": int | None,
            "requires_paywall": bool,
            "paywall_copy": Dict[str, str],
        }
        """
        cfg = config or default_pricing_config
        active_paid = self.is_active(user_key)
        record = self.get(user_key)
        queries_used_this_month = self.get_query_usage(user_key)

        if not cfg.pricing_model_enabled:
            return {
                "allowed": True,
                "tier": "paid" if active_paid else "free",
                "reason": "pricing_model_disabled",
                "queries_used": queries_used_this_month,
                "free_allowance": cfg.free_query_allowance,
                "queries_remaining": None,
                "requires_paywall": False,
                "paywall_copy": {},
            }

        if active_paid:
            bundle_remaining = record.get("bundle_queries_remaining") if record else None
            # If not explicitly tracked yet for legacy/subscription records, default to available
            is_exhausted = bundle_remaining is not None and bundle_remaining <= 0
            if is_exhausted:
                return {
                    "allowed": False,
                    "tier": "paid",
                    "reason": "bundle_queries_exhausted",
                    "queries_used": queries_used_this_month,
                    "free_allowance": cfg.free_query_allowance,
                    "queries_remaining": 0,
                    "requires_paywall": True,
                    "paywall_copy": {
                        "headline": cfg.paywall_headline,
                        "description": "You have completed the queries in your Review Bundle. Purchase an additional bundle to continue.",
                        "bundle_id": cfg.bundle_id,
                        "price": cfg.bundle_price_usd,
                        "variant": cfg.paywall_copy_variant,
                    },
                }
            return {
                "allowed": True,
                "tier": "paid",
                "reason": "paid_entitlement_active",
                "queries_used": queries_used_this_month,
                "free_allowance": cfg.free_query_allowance,
                "queries_remaining": bundle_remaining if bundle_remaining is not None else cfg.bundle_query_allowance,
                "requires_paywall": False,
                "paywall_copy": {},
            }

        # Free tier user
        if queries_used_this_month >= cfg.free_query_allowance:
            return {
                "allowed": False,
                "tier": "free",
                "reason": "free_query_allowance_exceeded",
                "queries_used": queries_used_this_month,
                "free_allowance": cfg.free_query_allowance,
                "queries_remaining": 0,
                "requires_paywall": True,
                "paywall_copy": {
                    "headline": cfg.paywall_headline,
                    "description": cfg.paywall_description,
                    "bundle_id": cfg.bundle_id,
                    "bundle_name": cfg.bundle_name,
                    "price": cfg.bundle_price_usd,
                    "queries_included": cfg.bundle_query_allowance,
                    "variant": cfg.paywall_copy_variant,
                },
            }

        return {
            "allowed": True,
            "tier": "free",
            "reason": "free_query_available",
            "queries_used": queries_used_this_month,
            "free_allowance": cfg.free_query_allowance,
            "queries_remaining": max(0, cfg.free_query_allowance - queries_used_this_month),
            "requires_paywall": False,
            "paywall_copy": {},
        }

    def credit_bundle(self, user_key: str, bundle_id: str, query_allowance: Optional[int] = None):
        cfg = default_pricing_config
        queries = query_allowance if query_allowance is not None else cfg.bundle_query_allowance
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as connection:
            existing = connection.execute("SELECT * FROM entitlements WHERE user_key = ?", (user_key,)).fetchone()
            if existing:
                current_rem = existing["bundle_queries_remaining"] or 0
                connection.execute(
                    """
                    UPDATE entitlements
                    SET provider = 'bundle', provider_id = ?, plan = ?, status = 'ACTIVE',
                        bundle_queries_remaining = ?, updated_at = ?
                    WHERE user_key = ?
                    """,
                    (f"bundle_{user_key}_{int(datetime.now(timezone.utc).timestamp())}", bundle_id, current_rem + queries, now_iso, user_key),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO entitlements
                    (user_key, provider, provider_id, plan, status, starts_at, updated_at, bundle_queries_remaining, total_queries_used)
                    VALUES (?, 'bundle', ?, ?, 'ACTIVE', ?, ?, ?, 0)
                    """,
                    (
                        user_key,
                        f"bundle_{user_key}_{int(datetime.now(timezone.utc).timestamp())}",
                        bundle_id,
                        now_iso,
                        now_iso,
                        queries,
                    ),
                )

    def claim_event(self, event_id: str) -> bool:
        """Return False for a replayed webhook event."""
        if not event_id:
            raise ValueError("event_id is required.")
        if self.supabase:
            try:
                self.supabase.insert("payment_events", {"event_id": event_id})
                return True
            except SupabaseRequestError as error:
                if error.status_code == 409:
                    return False
                raise
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO payment_events(event_id, received_at) VALUES (?, ?)",
                (event_id, datetime.now(timezone.utc).isoformat()),
            )
            return cursor.rowcount == 1
