from unittest.mock import MagicMock
from app.payments.entitlements import EntitlementStore
from app.analytics.event_store import AnalyticsEventStore


def test_entitlement_store_supabase_query_usage(monkeypatch, tmp_path):
    mock_client = MagicMock()
    # Mock GET user_query_usage returning 1 count
    mock_client.request.return_value = [{"query_count": 1}]

    monkeypatch.setattr("app.payments.entitlements.SupabaseRestClient.from_env", lambda: mock_client)

    db_file = str(tmp_path / "test_entitlements.sqlite3")
    store = EntitlementStore(database_path=db_file)
    assert store.supabase is not None
    assert store.database_path is not None

    count = store.get_query_usage("test-user-uuid", "2026-10")
    assert count == 1


def test_entitlement_store_supabase_fallback_on_error(monkeypatch, tmp_path):
    mock_client = MagicMock()
    mock_client.request.side_effect = RuntimeError("Supabase network error")

    monkeypatch.setattr("app.payments.entitlements.SupabaseRestClient.from_env", lambda: mock_client)

    db_file = str(tmp_path / "test_entitlements_fallback.sqlite3")
    store = EntitlementStore(database_path=db_file)
    assert store.supabase is mock_client

    # Should not crash, should fall back to local sqlite storage (or 0)
    count = store.get_query_usage("test-fallback-user", "2026-10")
    assert count == 0

    new_count = store.increment_query_usage("test-fallback-user", "2026-10")
    assert new_count == 1


def test_analytics_event_store_supabase_ab_conversion(monkeypatch, tmp_path):
    mock_client = MagicMock()
    mock_client.request.return_value = [
        {
            "event_name": "query_submitted",
            "user_id": "user-1",
            "session_id": "sess-1",
            "occurred_at": "2026-10-02T10:00:00Z",
            "properties": {"tier": "free", "run_id": "run-1", "variant": "variant_a"},
        },
        {
            "event_name": "results_viewed",
            "user_id": "user-1",
            "session_id": "sess-1",
            "occurred_at": "2026-10-02T10:01:00Z",
            "properties": {"run_id": "run-1", "variant": "variant_a"},
        },
        {
            "event_name": "exclusion_row_opened",
            "user_id": "user-1",
            "session_id": "sess-1",
            "occurred_at": "2026-10-02T10:02:00Z",
            "properties": {"source_id": "src-1", "is_excluded_row": True, "variant": "variant_a"},
        },
    ]

    monkeypatch.setattr("app.analytics.event_store.SupabaseRestClient.from_env", lambda: mock_client)

    db_file = str(tmp_path / "test_analytics.sqlite3")
    event_store = AnalyticsEventStore(database_path=db_file)
    assert event_store.supabase is mock_client

    metrics = event_store.ab_conversion_metrics(days=30)
    assert "overall" in metrics
    assert "variant_a" in metrics
    assert "variant_b" in metrics
    assert metrics["overall"]["unique_users"] == 1
    assert metrics["overall"]["avg_time_to_first_exclusion_seconds"] == 120.0
