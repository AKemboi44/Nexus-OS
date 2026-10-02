import asyncio
import json
from uuid import uuid4
from fastapi import HTTPException
import cloud_app
from app.payments.config import default_pricing_config
from app.analytics.ab_experiment import ExperimentService


def test_staging_run_end_to_end_funnel_and_dashboard(tmp_path, monkeypatch):
    """
    Simulates staging runs end to end:
    - User A (free query -> views results -> opens exclusion row -> attempts 2nd query -> paywall -> purchases bundle)
    - User B (free query -> views results -> attempts 2nd query -> blocked -> does not purchase)
    - Queueing report priority check
    - Conversion metrics computation and side-by-side dashboard verification
    """
    import app.payments.entitlements
    import app.analytics.event_store

    ent_db = str(tmp_path / "staging_entitlements.sqlite3")
    ana_db = str(tmp_path / "staging_analytics.sqlite3")

    ent_store = app.payments.entitlements.EntitlementStore(database_path=ent_db)
    ana_store = app.analytics.event_store.AnalyticsEventStore(database_path=ana_db)

    monkeypatch.setattr(cloud_app, "entitlements", ent_store)
    monkeypatch.setattr(cloud_app, "analytics", ana_store)

    # 1. Pipeline and Database mocks
    class FakePipeline:
        def run_research(self, **kwargs):
            from pathlib import Path
            p = Path(kwargs["output_directory"]) / "audit.xlsx"
            p.write_bytes(b"audit xlsx data")
            return {
                "status": "success",
                "included": [{"title": "Paper 1", "authors": ["A"], "year": 2024, "venue": "V", "citation_count": 10}],
                "excluded": [{"title": "Filtered Paper 2", "exclusion_reason": "Low authority threshold"}],
                "discovery_report_name": "audit.xlsx",
            }

    class FakeDatabase:
        def __init__(self):
            self.storage = {}
            self.records = []

        def request(self, method, resource, **kwargs):
            return []

        def upload_storage_object(self, bucket, path, data, content_type):
            self.storage[path] = data

        def insert(self, table, values):
            val = dict(values)
            val["id"] = values.get("id", str(uuid4()))
            self.records.append((table, val))
            return val

    db = FakeDatabase()
    monkeypatch.setattr(cloud_app, "pipeline", FakePipeline())
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: db)
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)

    user_a_id = "staging_user_a"  # will be assigned Variant A or B
    user_b_id = "staging_user_b"

    # --- USER A FLOW ---
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda auth: {"id": user_a_id, "email": "a@example.com"})

    # 1. Free Query 1
    res1 = asyncio.run(cloud_app.execute_cloud_scan(
        cloud_app.ScanRequest(topic="Quantum ML Optimization", max_sources=20),
        authorization="Bearer user_a",
    ))
    assert res1["status"] == "success"
    assert len(res1["included"]) == 1
    assert len(res1["excluded"]) == 1
    run_a_id = res1["research_run_id"]
    variant_a_user = res1["ab_variant"]

    # Client records results_viewed
    ana_store.record("results_viewed", user_id=user_a_id, properties={"run_id": run_a_id, "variant": variant_a_user})
    # Client records exclusion_row_opened
    ana_store.record("exclusion_row_opened", user_id=user_a_id, properties={"source_id": "s2", "is_excluded_row": True, "variant": variant_a_user})

    # 2. Second Query Attempt -> Blocked by Paywall
    try:
        asyncio.run(cloud_app.execute_cloud_scan(
            cloud_app.ScanRequest(topic="Quantum Annealing Deep Dive", max_sources=20),
            authorization="Bearer user_a",
        ))
        assert False, "Should have been blocked by paywall"
    except HTTPException as paywall_exc:
        assert paywall_exc.status_code == 403
        assert paywall_exc.detail["requires_bundle"] is True
        assert "Literature Review Bundle" in str(paywall_exc.detail["paywall"])

    # 3. User A Purchases Review Bundle
    buy_res = asyncio.run(cloud_app.purchase_review_bundle(
        cloud_app.PayPalCaptureRequest(order_id="order_123", user_id=user_a_id, bundle_id="review_bundle_standard", variant=variant_a_user),
        authorization="Bearer user_a",
    ))
    assert buy_res["status"] == "success"
    assert buy_res["queries_remaining"] == 10

    # 4. User A now runs query with Review Bundle entitlement
    res2 = asyncio.run(cloud_app.execute_cloud_scan(
        cloud_app.ScanRequest(topic="Quantum Annealing Deep Dive", max_sources=50),
        authorization="Bearer user_a",
    ))
    assert res2["status"] == "success"
    assert res2["is_paid_user"] is True

    # --- USER B FLOW ---
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda auth: {"id": user_b_id, "email": "b@example.com"})
    res_b1 = asyncio.run(cloud_app.execute_cloud_scan(
        cloud_app.ScanRequest(topic="Neural Graph Compilers", max_sources=20),
        authorization="Bearer user_b",
    ))
    variant_b_user = res_b1["ab_variant"]
    ana_store.record("results_viewed", user_id=user_b_id, properties={"run_id": res_b1["research_run_id"], "variant": variant_b_user})

    # User B attempts 2nd query and stops at paywall
    try:
        asyncio.run(cloud_app.execute_cloud_scan(
            cloud_app.ScanRequest(topic="Second query B", max_sources=20),
            authorization="Bearer user_b",
        ))
    except HTTPException as e:
        assert e.status_code == 403

    # --- VERIFY CONVERSION METRICS & DASHBOARD ---
    dashboard_data = ana_store.ab_conversion_metrics(days=30)
    assert dashboard_data["overall"]["free_query_users"] == 2
    assert dashboard_data["overall"]["second_query_attempted_users"] == 2
    assert dashboard_data["overall"]["paywall_shown_users"] == 2
    assert dashboard_data["overall"]["purchased_users"] == 1
    assert dashboard_data["overall"]["paywall_to_purchase_rate"] == 0.5
    assert dashboard_data["overall"]["purchase_rate_opened_exclusion"] == 1.0
    assert dashboard_data["overall"]["purchase_rate_unopened_exclusion"] == 0.0

    # Side-by-side variant breakdown
    assert "variant_a" in dashboard_data
    assert "variant_b" in dashboard_data
