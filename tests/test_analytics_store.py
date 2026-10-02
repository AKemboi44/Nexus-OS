from app.analytics.event_store import AnalyticsEventStore


def test_analytics_store_builds_funnel_and_error_summary(tmp_path):
    store = AnalyticsEventStore(str(tmp_path / "events.sqlite3"))
    store.record("scan_started", "user-1", "session-1")
    store.record("scan_completed", "user-1", "session-1")
    store.record("error", "user-1", "session-1", {"error_code": "RATE_LIMIT"})

    summary = store.summary(days=30)

    assert any(item["event_name"] == "scan_started" for item in summary["events"])
    assert any(item["stage"] == "scan_completed" and item["unique_users"] == 1 for item in summary["funnel"])
    assert summary["common_errors"][0]["error_code"] == "RATE_LIMIT"


def test_analytics_store_reports_aggregate_operational_metrics(tmp_path):
    store = AnalyticsEventStore(str(tmp_path / "events.sqlite3"))
    store.record("report_completed", "user-1", "backend", {
        "duration_ms": 1200,
        "cache_hit": True,
        "report_type": "proposal",
    })
    store.record("report_completed", "user-1", "backend", {
        "duration_ms": 800,
        "cache_hit": False,
        "report_type": "proposal",
    })

    summary = store.summary(days=30)
    metric = next(item for item in summary["operational_metrics"] if item["event_name"] == "report_completed")

    assert metric == {
        "event_name": "report_completed",
        "event_count": 2,
        "timed_events": 2,
        "average_duration_ms": 1000.0,
        "cache_hits": 1,
    }
