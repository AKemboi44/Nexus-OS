from app.analytics.event_store import AnalyticsEventStore


def test_analytics_store_builds_funnel_and_error_summary(tmp_path):
    store = AnalyticsEventStore(str(tmp_path / "events.sqlite3"))
    store.record("scan_started", "user-1", "session-1")
    store.record("scan_completed", "user-1", "session-1")
    store.record("error", "user-1", "session-1", {"error_code": "RATE_LIMIT", "message": "Provider limit"})

    summary = store.summary(days=30)

    assert any(item["event_name"] == "scan_started" for item in summary["events"])
    assert any(item["stage"] == "scan_completed" and item["unique_users"] == 1 for item in summary["funnel"])
    assert summary["common_errors"][0]["error_code"] == "RATE_LIMIT"
