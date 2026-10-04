import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from app.supabase_store import SupabaseRequestError, SupabaseRestClient
from app.payments.catalog import Pack, money
from app.payments.config import default_pricing_config, PricingConfig

PACK_PROVIDERS = ("pack", "bundle")


def parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class EntitlementStore:
    """Durable server-side subscription state used to authorize paid features."""

    def __init__(self, database_path: str = None):
        self.supabase = SupabaseRestClient.from_env()
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
                CREATE TABLE IF NOT EXISTS payment_orders (
                    order_id TEXT PRIMARY KEY,
                    user_key TEXT NOT NULL,
                    pack_id TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    capture_id TEXT,
                    created_at TEXT NOT NULL,
                    captured_at TEXT,
                    credited_at TEXT,
                    refunded_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_payment_orders_capture ON payment_orders(capture_id)"
            )
            try:
                connection.execute("ALTER TABLE payment_events ADD COLUMN processed_at TEXT")
            except Exception:
                pass
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_feature_usage (
                    user_key TEXT NOT NULL,
                    feature TEXT NOT NULL,
                    period_month TEXT NOT NULL,
                    use_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_key, feature, period_month)
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

    def is_active(self, user_key: str, user_email: Optional[str] = None) -> bool:
        cfg = default_pricing_config
        if user_email and user_email.strip().lower() in cfg.whitelisted_emails:
            return True
        if user_key and user_key.strip().lower() in cfg.whitelisted_emails:
            return True
        record = self.get(user_key)
        if not (record and record["status"] in {"ACTIVE", "APPROVED", "COMPLETED"}):
            return False
        ends_at = parse_time(record.get("ends_at"))
        return not (ends_at and ends_at <= datetime.now(timezone.utc))

    @staticmethod
    def current_period_month() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def get_query_usage(self, user_key: str, period_month: Optional[str] = None) -> int:
        period = period_month or self.current_period_month()
        if self.supabase:
            try:
                rows = self.supabase.request(
                    "GET",
                    "user_query_usage",
                    params={
                        "user_id": f"eq.{user_key}",
                        "period_month": f"eq.{period}",
                        "select": "query_count",
                        "limit": 1,
                    },
                )
                if isinstance(rows, list) and rows:
                    return int(rows[0].get("query_count") or 0)
                return 0
            except Exception:
                # Fallback to local store if Supabase fails or table not yet migrated
                pass
        with self._connect() as connection:
            row = connection.execute(
                "SELECT query_count FROM user_query_usage WHERE user_key = ? AND period_month = ?",
                (user_key, period),
            ).fetchone()
        return int(row["query_count"]) if row else 0

    def increment_query_usage(self, user_key: str, period_month: Optional[str] = None) -> int:
        period = period_month or self.current_period_month()
        now_iso = datetime.now(timezone.utc).isoformat()
        if self.supabase:
            try:
                existing_rows = self.supabase.request(
                    "GET",
                    "user_query_usage",
                    params={
                        "user_id": f"eq.{user_key}",
                        "period_month": f"eq.{period}",
                        "select": "query_count",
                        "limit": 1,
                    },
                )
                if isinstance(existing_rows, list) and existing_rows:
                    new_count = int(existing_rows[0].get("query_count") or 0) + 1
                    self.supabase.request(
                        "PATCH",
                        "user_query_usage",
                        params={
                            "user_id": f"eq.{user_key}",
                            "period_month": f"eq.{period}",
                        },
                        json={
                            "query_count": new_count,
                            "last_queried_at": now_iso,
                        },
                    )
                else:
                    new_count = 1
                    self.supabase.request(
                        "POST",
                        "user_query_usage",
                        json={
                            "user_id": user_key,
                            "period_month": period,
                            "query_count": 1,
                            "last_queried_at": now_iso,
                        },
                    )
                # Also update bundle remaining in supabase if user has bundle entitlement
                try:
                    entitlement = self.get(user_key)
                    if entitlement and entitlement.get("bundle_queries_remaining") is not None:
                        rem = max(0, int(entitlement["bundle_queries_remaining"]) - 1)
                        tot = int(entitlement.get("total_queries_used") or 0) + 1
                        self.supabase.request(
                            "PATCH",
                            "entitlements",
                            params={"user_id": f"eq.{user_key}"},
                            json={
                                "bundle_queries_remaining": rem,
                                "total_queries_used": tot,
                                "updated_at": now_iso,
                            },
                        )
                except Exception:
                    pass
                return new_count
            except Exception:
                # Fall back to local SQLite on any Supabase error
                pass

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
            try:
                entitlement = self.get(user_key)
            except Exception:
                entitlement = None
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
        user_email: Optional[str] = None,
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
        
        # Check whitelist bypass (unlimited queries and full paid privileges)
        normalized_email = str(user_email or "").strip().lower()
        normalized_key = str(user_key or "").strip().lower()
        if (
            normalized_email in cfg.whitelisted_emails
            or normalized_key in cfg.whitelisted_emails
        ):
            queries_used_this_month = self.get_query_usage(user_key)
            return {
                "allowed": True,
                "tier": "paid",
                "reason": "whitelisted_admin",
                "queries_used": queries_used_this_month,
                "free_allowance": cfg.free_query_allowance,
                "queries_remaining": None,
                "requires_paywall": False,
                "paywall_copy": {},
            }

        try:
            active_paid = self.is_active(user_key, user_email=user_email)
        except TypeError:
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
                        "description": "You have used all the scans in your Research Pack. Buy another pack to keep scanning.",
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
        if self.supabase:
            try:
                existing = self.get(user_key)
                provider_id = f"bundle_{user_key}_{int(datetime.now(timezone.utc).timestamp())}"
                if existing:
                    current_rem = existing.get("bundle_queries_remaining") or 0
                    self.supabase.request(
                        "PATCH",
                        "entitlements",
                        params={"user_id": f"eq.{user_key}"},
                        json={
                            "provider": "bundle",
                            "provider_id": provider_id,
                            "plan": bundle_id,
                            "status": "ACTIVE",
                            "bundle_queries_remaining": current_rem + queries,
                            "updated_at": now_iso,
                        },
                    )
                else:
                    self.supabase.request(
                        "POST",
                        "entitlements",
                        json={
                            "user_id": user_key,
                            "provider": "bundle",
                            "provider_id": provider_id,
                            "plan": bundle_id,
                            "status": "ACTIVE",
                            "starts_at": now_iso,
                            "updated_at": now_iso,
                            "bundle_queries_remaining": queries,
                            "total_queries_used": 0,
                        },
                    )
                return
            except Exception:
                # Fall back to local SQLite on any Supabase error
                pass

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

    # --- webhook bookkeeping: an event is final only after it was processed successfully ---

    def begin_event(self, event_id: str) -> bool:
        """True when this event still needs processing (new, or an earlier attempt failed)."""
        if not event_id:
            raise ValueError("event_id is required.")
        if self.supabase:
            try:
                self.supabase.insert("payment_events", {"event_id": event_id})
                return True
            except SupabaseRequestError as error:
                if error.status_code != 409:
                    raise
            rows = self.supabase.request(
                "GET", "payment_events",
                params={"event_id": f"eq.{event_id}", "select": "processed_at", "limit": 1},
            )
            return not (rows and rows[0].get("processed_at"))
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO payment_events(event_id, received_at) VALUES (?, ?)",
                (event_id, datetime.now(timezone.utc).isoformat()),
            )
            if cursor.rowcount == 1:
                return True
            row = connection.execute(
                "SELECT processed_at FROM payment_events WHERE event_id = ?", (event_id,)
            ).fetchone()
            return not (row and row["processed_at"])

    def finish_event(self, event_id: str) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        if self.supabase:
            self.supabase.request(
                "PATCH", "payment_events",
                params={"event_id": f"eq.{event_id}"}, json={"processed_at": now_iso},
            )
            return
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE payment_events SET processed_at = ? WHERE event_id = ?", (now_iso, event_id)
            )

    # --- pack orders. Payments never fall back to the ephemeral local file when Supabase fails. ---

    @staticmethod
    def _order_view(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not row:
            return None
        return {
            "order_id": row["order_id"],
            "user_id": str(row.get("user_id") or row.get("user_key")),
            "pack_id": row["pack_id"],
            "amount": money(row["amount"]),
            "currency": row["currency"],
            "status": row["status"],
            "capture_id": row.get("capture_id"),
        }

    def create_order(self, order_id: str, user_key: str, pack: Pack) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        if self.supabase:
            self.supabase.insert("payment_orders", {
                "order_id": order_id, "user_id": user_key, "pack_id": pack.id,
                "amount": pack.price_text, "currency": pack.currency, "status": "pending",
            })
            return
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO payment_orders (order_id, user_key, pack_id, amount, currency, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                (order_id, user_key, pack.id, pack.price_text, pack.currency, now_iso),
            )

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase:
            rows = self.supabase.request(
                "GET", "payment_orders",
                params={"order_id": f"eq.{order_id}", "select": "*", "limit": 1},
            )
            return self._order_view(rows[0] if rows else None)
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM payment_orders WHERE order_id = ?", (order_id,)).fetchone()
        return self._order_view(dict(row) if row else None)

    def get_order_by_capture(self, capture_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase:
            rows = self.supabase.request(
                "GET", "payment_orders",
                params={"capture_id": f"eq.{capture_id}", "select": "*", "limit": 1},
            )
            return self._order_view(rows[0] if rows else None)
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM payment_orders WHERE capture_id = ?", (capture_id,)).fetchone()
        return self._order_view(dict(row) if row else None)

    def mark_order(self, order_id: str, from_status: str, to_status: str, capture_id: Optional[str] = None) -> bool:
        """Move an order between states only if it is still in `from_status`."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if self.supabase:
            body: Dict[str, Any] = {"status": to_status}
            if capture_id:
                body["capture_id"] = capture_id
            if to_status == "captured":
                body["captured_at"] = now_iso
            rows = self.supabase.request(
                "PATCH", "payment_orders",
                params={"order_id": f"eq.{order_id}", "status": f"eq.{from_status}"},
                json=body, prefer="return=representation",
            )
            return bool(rows)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE payment_orders SET status = ?, capture_id = COALESCE(?, capture_id), "
                "captured_at = CASE WHEN ? = 'captured' THEN ? ELSE captured_at END "
                "WHERE order_id = ? AND status = ?",
                (to_status, capture_id, to_status, now_iso, order_id, from_status),
            )
            return cursor.rowcount == 1

    def credit_pack_order(self, order: Dict[str, Any], pack: Pack, capture_id: Optional[str]) -> Dict[str, Any]:
        """Credit a paid order exactly once. Returns {"credited": False} if it already was."""
        if self.supabase:
            result = self.supabase.request(
                "POST", "rpc/nexus_credit_pack",
                json={
                    "p_order_id": order["order_id"], "p_user_id": order["user_id"], "p_pack_id": pack.id,
                    "p_scans": pack.scans, "p_validity_days": pack.validity_days, "p_capture_id": capture_id,
                },
            )
            if not isinstance(result, dict):
                raise RuntimeError("Supabase returned an invalid pack credit result.")
            return result

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        user_key = order["user_id"]
        with self._lock, self._connect() as connection:
            flipped = connection.execute(
                "UPDATE payment_orders SET status = 'credited', capture_id = COALESCE(?, capture_id), "
                "captured_at = COALESCE(captured_at, ?), credited_at = ? "
                "WHERE order_id = ? AND user_key = ? AND status IN ('pending', 'captured')",
                (capture_id, now_iso, now_iso, order["order_id"], user_key),
            ).rowcount
            if flipped != 1:
                return {"credited": False}
            existing = connection.execute("SELECT * FROM entitlements WHERE user_key = ?", (user_key,)).fetchone()
            provider_id = f"pack_{order['order_id']}"
            if existing is None:
                new_end = now + timedelta(days=pack.validity_days)
                connection.execute(
                    "INSERT INTO entitlements (user_key, provider, provider_id, plan, status, starts_at, ends_at, "
                    "updated_at, bundle_queries_remaining, total_queries_used) "
                    "VALUES (?, 'pack', ?, ?, 'ACTIVE', ?, ?, ?, ?, 0)",
                    (user_key, provider_id, pack.id, now_iso, new_end.isoformat(), now_iso, pack.scans),
                )
            elif (
                existing["status"] == "ACTIVE"
                and existing["bundle_queries_remaining"] is None
                and existing["provider"] not in PACK_PROVIDERS
            ):
                return {"credited": True, "ends_at": existing["ends_at"], "scans_added": 0, "unlimited": True}
            else:
                base = max(parse_time(existing["ends_at"]) or now, now)
                new_end = base + timedelta(days=pack.validity_days)
                connection.execute(
                    "UPDATE entitlements SET provider = 'pack', provider_id = ?, plan = ?, status = 'ACTIVE', "
                    "ends_at = ?, bundle_queries_remaining = COALESCE(bundle_queries_remaining, 0) + ?, "
                    "updated_at = ? WHERE user_key = ?",
                    (provider_id, pack.id, new_end.isoformat(), pack.scans, now_iso, user_key),
                )
        return {"credited": True, "ends_at": new_end.isoformat(), "scans_added": pack.scans}

    # --- monthly allowances for free-tier features. Unlike the scan counter these never fall back to
    # the ephemeral local file when Supabase fails: a failed claim means "not granted". ---

    def claim_feature_use(self, user_key: str, feature: str, limit: int) -> bool:
        """Take one use of `feature` this month if any are left. Atomic."""
        if limit <= 0:
            return False
        period = self.current_period_month()
        if self.supabase:
            result = self.supabase.request(
                "POST", "rpc/nexus_claim_feature_use",
                json={"p_user_id": user_key, "p_feature": feature, "p_period": period, "p_limit": limit},
            )
            return int(result) > 0
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO user_feature_usage (user_key, feature, period_month, use_count) "
                "VALUES (?, ?, ?, 0)",
                (user_key, feature, period),
            )
            claimed = connection.execute(
                "UPDATE user_feature_usage SET use_count = use_count + 1 "
                "WHERE user_key = ? AND feature = ? AND period_month = ? AND use_count < ?",
                (user_key, feature, period, limit),
            ).rowcount
        return claimed == 1

    def release_feature_use(self, user_key: str, feature: str) -> None:
        """Give back a use that was claimed but never delivered."""
        period = self.current_period_month()
        if self.supabase:
            self.supabase.request(
                "POST", "rpc/nexus_release_feature_use",
                json={"p_user_id": user_key, "p_feature": feature, "p_period": period},
            )
            return
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE user_feature_usage SET use_count = MAX(0, use_count - 1) "
                "WHERE user_key = ? AND feature = ? AND period_month = ?",
                (user_key, feature, period),
            )

    def purchase_summary(self, user_key: str) -> List[Dict[str, Any]]:
        """Packs this user has bought and kept (credited, not refunded), newest first."""
        if self.supabase:
            rows = self.supabase.request(
                "GET", "payment_orders",
                params={"user_id": f"eq.{user_key}", "status": "eq.credited",
                        "select": "order_id,pack_id,credited_at", "order": "credited_at.desc"},
            ) or []
        else:
            with self._connect() as connection:
                rows = [dict(row) for row in connection.execute(
                    "SELECT order_id, pack_id, credited_at FROM payment_orders "
                    "WHERE user_key = ? AND status = 'credited' ORDER BY credited_at DESC",
                    (user_key,),
                ).fetchall()]
        return [{"order_id": row["order_id"], "pack_id": row["pack_id"], "credited_at": row.get("credited_at")}
                for row in rows]

    def refund_pack_order(self, order_id: str, pack: Pack) -> Dict[str, Any]:
        """Undo a credited pack after a refund or reversal. Idempotent."""
        if self.supabase:
            result = self.supabase.request(
                "POST", "rpc/nexus_refund_pack",
                json={"p_order_id": order_id, "p_scans": pack.scans, "p_validity_days": pack.validity_days},
            )
            if not isinstance(result, dict):
                raise RuntimeError("Supabase returned an invalid pack refund result.")
            return result

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        with self._lock, self._connect() as connection:
            order = connection.execute("SELECT * FROM payment_orders WHERE order_id = ?", (order_id,)).fetchone()
            if order is None or order["status"] not in ("credited", "captured"):
                return {"refunded": False}
            connection.execute(
                "UPDATE payment_orders SET status = 'refunded', refunded_at = ? WHERE order_id = ?",
                (now_iso, order_id),
            )
            if order["status"] == "credited":
                ent = connection.execute(
                    "SELECT * FROM entitlements WHERE user_key = ?", (order["user_key"],)
                ).fetchone()
                if ent is not None and ent["provider"] in PACK_PROVIDERS:
                    remaining = max(0, (ent["bundle_queries_remaining"] or 0) - pack.scans)
                    if remaining == 0:
                        ends_at, status = now_iso, "CANCELLED"
                    else:
                        current_end = parse_time(ent["ends_at"]) or now
                        ends_at = max(now, current_end - timedelta(days=pack.validity_days)).isoformat()
                        status = ent["status"]
                    connection.execute(
                        "UPDATE entitlements SET bundle_queries_remaining = ?, ends_at = ?, status = ?, "
                        "updated_at = ? WHERE user_key = ?",
                        (remaining, ends_at, status, now_iso, order["user_key"]),
                    )
        return {"refunded": True, "was_credited": order["status"] == "credited"}
