import json
import pytest
from datetime import datetime, timezone
from app.payments.config import PricingConfig, default_pricing_config
from app.payments.entitlements import EntitlementStore
from app.analytics.ab_experiment import ExperimentService
from app.analytics.event_store import AnalyticsEventStore
from app.reports.report_queue import ReportQueueManager, QueuedReportJob


def test_pricing_config_and_feature_flag(monkeypatch):
    monkeypatch.setenv("NEXUS_PRICING_MODEL_ENABLED", "true")
    monkeypatch.setenv("NEXUS_FREE_QUERY_ALLOWANCE", "1")
    monkeypatch.setenv("NEXUS_BUNDLE_QUERY_ALLOWANCE", "10")
    monkeypatch.setenv("NEXUS_BUNDLE_PRICE_USD", "29.00")
    monkeypatch.setenv("NEXUS_WHITELISTED_EMAILS", "akiptoo20@gmail.com,admin@nexus.test")

    cfg = PricingConfig.from_env()
    assert cfg.pricing_model_enabled is True
    assert cfg.free_query_allowance == 1
    assert cfg.bundle_query_allowance == 10
    assert cfg.bundle_price_usd == 29.00
    assert cfg.bundle_id == "starter_20"
    assert "akiptoo20@gmail.com" in cfg.whitelisted_emails
    assert "admin@nexus.test" in cfg.whitelisted_emails


def test_default_whitelist_includes_both_admins(monkeypatch):
    monkeypatch.delenv("NEXUS_WHITELISTED_EMAILS", raising=False)

    assert {"akiptoo20@gmail.com", "hildakiptoo97@gmail.com"} <= PricingConfig.from_env().whitelisted_emails
    assert {"akiptoo20@gmail.com", "hildakiptoo97@gmail.com"} <= PricingConfig().whitelisted_emails


@pytest.mark.parametrize("whitelisted_email", ["akiptoo20@gmail.com", "hildakiptoo97@gmail.com"])
def test_whitelisted_user_unlimited_privileges(tmp_path, whitelisted_email):
    db_path = str(tmp_path / "test_entitlements_whitelist.sqlite3")
    store = EntitlementStore(database_path=db_path)
    user_id = "user_whitelisted_123"

    # Even after 10 queries, whitelisted user is still allowed with paid tier
    for _ in range(10):
        store.increment_query_usage(user_id)
    
    assert store.get_query_usage(user_id) == 10
    perm = store.check_query_permission(user_id, user_email=whitelisted_email)
    assert perm["allowed"] is True
    assert perm["tier"] == "paid"
    assert perm["reason"] == "whitelisted_admin"
    assert store.is_active(user_id, user_email=whitelisted_email) is True


def test_entitlements_free_query_allowance_and_paywall(tmp_path):
    db_path = str(tmp_path / "test_entitlements.sqlite3")
    store = EntitlementStore(database_path=db_path)
    user_id = "user_free_1"

    # 1st query should be allowed
    perm1 = store.check_query_permission(user_id)
    assert perm1["allowed"] is True
    assert perm1["tier"] == "free"
    assert perm1["queries_remaining"] == 1

    # Simulate running 1st query
    store.increment_query_usage(user_id)
    assert store.get_query_usage(user_id) == 1

    # 2nd query should be blocked by paywall
    perm2 = store.check_query_permission(user_id)
    assert perm2["allowed"] is False
    assert perm2["requires_paywall"] is True
    assert perm2["reason"] == "free_query_allowance_exceeded"
    assert perm2["paywall_copy"]["variant"] == "review_bundle_v1"
    assert perm2["paywall_copy"]["price"] == default_pricing_config.bundle_price_usd


def test_review_bundle_crediting_and_quota(tmp_path):
    db_path = str(tmp_path / "test_entitlements_bundle.sqlite3")
    store = EntitlementStore(database_path=db_path)
    user_id = "user_bundle_1"

    # User uses 1st free query
    store.increment_query_usage(user_id)
    assert store.check_query_permission(user_id)["allowed"] is False

    # Purchase review bundle
    store.credit_bundle(user_id, bundle_id="review_bundle_standard", query_allowance=10)
    assert store.is_active(user_id) is True

    # User now has active bundle
    perm = store.check_query_permission(user_id)
    assert perm["allowed"] is True
    assert perm["tier"] == "paid"
    assert perm["queries_remaining"] == 10

    # User runs query from bundle
    store.increment_query_usage(user_id)
    ent = store.get(user_id)
    assert ent["bundle_queries_remaining"] == 9
    assert ent["total_queries_used"] == 1


def test_ab_experiment_assignment():
    variant_1 = ExperimentService.get_variant_for_user("user_abc")
    variant_2 = ExperimentService.get_variant_for_user("user_abc")
    assert variant_1 == variant_2
    assert variant_1 in (ExperimentService.VARIANT_A, ExperimentService.VARIANT_B)


def test_report_queue_paid_priority():
    mgr = ReportQueueManager()
    # Free user job
    job_free = mgr.enqueue(
        user_id="free_user",
        topic="Free Topic",
        is_paid=False,
    )
    assert job_free.priority == 0

    # Paid user job
    job_paid = mgr.enqueue(
        user_id="paid_user",
        topic="Paid Topic",
        is_paid=True,
    )
    assert job_paid.priority == 10

    # Verify order in processing candidates
    candidate_jobs = [j for j in mgr._jobs.values() if j.status in ("queued", "generating")]
    candidate_jobs.sort(key=lambda j: (-j.priority, j.created_timestamp))
    assert candidate_jobs[0].id == job_paid.id
    assert candidate_jobs[1].id == job_free.id


def test_ab_conversion_metrics_computation(tmp_path):
    db_path = str(tmp_path / "test_analytics_ab.sqlite3")
    store = AnalyticsEventStore(database_path=db_path)

    # User 1 (Variant A): Free query -> opened exclusion -> 2nd query -> paywall -> purchased bundle
    store.record("query_submitted", user_id="u1", properties={"tier": "free", "run_id": "r1", "variant": "variant_a"})
    store.record("results_viewed", user_id="u1", properties={"run_id": "r1", "variant": "variant_a"})
    store.record("exclusion_row_opened", user_id="u1", properties={"source_id": "s1", "is_excluded_row": True, "variant": "variant_a"})
    store.record("second_query_attempted", user_id="u1", properties={"run_id": "r2", "is_blocked": True, "variant": "variant_a"})
    store.record("paywall_shown", user_id="u1", properties={"variant": "variant_a"})
    store.record("bundle_purchased", user_id="u1", properties={"bundle_id": "review_bundle_standard", "price": 29.0, "variant": "variant_a"})

    # User 2 (Variant B): Free query -> did not open exclusion -> 2nd query -> paywall -> did not purchase
    store.record("query_submitted", user_id="u2", properties={"tier": "free", "run_id": "r3", "variant": "variant_b"})
    store.record("results_viewed", user_id="u2", properties={"run_id": "r3", "variant": "variant_b"})
    store.record("second_query_attempted", user_id="u2", properties={"run_id": "r4", "is_blocked": True, "variant": "variant_b"})
    store.record("paywall_shown", user_id="u2", properties={"variant": "variant_b"})

    # User 3 (Variant B): Free query -> abandoned (never viewed)
    store.record("query_submitted", user_id="u3", properties={"tier": "free", "run_id": "r5", "variant": "variant_b"})

    metrics = store.ab_conversion_metrics(days=30)
    assert "overall" in metrics
    assert "variant_a" in metrics
    assert "variant_b" in metrics

    va = metrics["variant_a"]
    vb = metrics["variant_b"]

    assert va["free_query_users"] == 1
    assert va["opened_exclusion_users"] == 1
    assert va["purchased_users"] == 1
    assert va["paywall_to_purchase_rate"] == 1.0
    assert va["free_query_abandonment_rate"] == 0.0

    assert vb["free_query_users"] == 2
    assert vb["opened_exclusion_users"] == 0
    assert vb["purchased_users"] == 0
    assert vb["free_query_abandonment_rate"] == 0.5  # 1 out of 2 runs not viewed
