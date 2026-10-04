"""Free users see a limited preview and never receive a file; paid users are unaffected."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import cloud_app
from app.analytics import schema
from app.payments import exposure
from app.payments.entitlements import EntitlementStore
from app.reports.proposal_service import generate_proposal_docx
from app.reports.snapshot import snapshot_from_docx
from tests.test_proposal_apa_rendering import SOURCES

RUN_A = "11111111-1111-4111-8111-111111111111"
RUN_B = "22222222-2222-4222-8222-222222222222"
OTHERS_RUN = "33333333-3333-4333-8333-333333333333"
AUTH = {"Authorization": "Bearer token"}
SECRET = "SECRET-HIDDEN-ROW"


def sources(count, prefix="Included"):
    return [{"uid": f"{prefix}-{i}", "title": f"{prefix} study {i} {SECRET if i >= 3 else ''}".strip(),
             "authors": ["Author, A."], "year": 2020, "venue": "Journal", "doi": f"10.1/{prefix}{i}",
             "abstract": f"{SECRET} abstract {i}", "source_contribution": f"{SECRET} contribution {i}",
             "inclusion_reason": "Peer reviewed", "exclusion_reason": "Too old"} for i in range(count)]


class FakeDatabase:
    def __init__(self):
        self.objects, self.runs, self.inserted, self.claims, self.reads = {}, {}, [], 0, []

    def request(self, method, table, params=None, json=None, **kwargs):
        if method == "GET" and table == "research_runs":
            row = self.runs.get(params["id"].removeprefix("eq."))
            return [row] if row and row["user_id"] == params["user_id"].removeprefix("eq.") else []
        if method == "GET" and table == "dossier_download_usage":
            return []
        if table == "rpc/nexus_claim_dossier_download":
            self.claims += 1
            return 2
        if method == "DELETE":
            return []
        raise AssertionError(f"unexpected request {method} {table}")

    def insert(self, table, values):
        record = {**values, "id": values.get("id") or f"{table}-{len(self.inserted) + 1}"}
        self.inserted.append((table, record))
        if table == "research_runs":
            self.runs[record["id"]] = record
        return record

    def upload_storage_object(self, bucket, path, content, content_type):
        self.objects[path] = content

    def download_storage_object(self, bucket, path):
        self.reads.append(path)
        if path not in self.objects:
            raise cloud_app.SupabaseRequestError(404, "not found")
        return self.objects[path]

    def delete_storage_object(self, bucket, path):
        self.objects.pop(path, None)


class World:
    def __init__(self, monkeypatch, tmp_path, fake_provider, synthesized_draft_json):
        self.db = FakeDatabase()
        self.store = EntitlementStore(str(tmp_path / "e.sqlite3"))
        self.user = {"id": "free-user", "email": "free@example.com"}
        self.paid = False
        self.events = []
        self.provider = fake_provider(content=synthesized_draft_json())
        self.generated_with = []
        monkeypatch.setattr(cloud_app, "entitlements", self.store)
        monkeypatch.setattr(self.store, "is_active", lambda user_id, user_email=None: self.paid)
        monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: dict(self.user))
        monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
        monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: self.db)
        monkeypatch.setattr(cloud_app.analytics, "record", lambda **event: self.events.append(event))
        monkeypatch.setattr("app.reports.proposal_service._default_provider", lambda: self.provider)
        real = cloud_app.generate_proposal_docx

        def spy(topic, domain, included, provider=None, ledger=None):
            self.generated_with.append(included)
            return real(topic, domain, included, provider, ledger)

        monkeypatch.setattr(cloud_app, "generate_proposal_docx", spy)
        self.client = TestClient(cloud_app.app)

    def seed_run(self, run_id, user="free-user", included=None, excluded=None):
        included = [dict(s) for s in (SOURCES if included is None else included)]
        name = "research_audit_x_20261001_120000.xlsx"
        self.db.runs[run_id] = {
            "id": run_id, "user_id": user, "query": "Ethical AI", "created_at": "2026-10-01",
            "result": {"query": "Ethical AI", "status": "success", "discovery_report_name": name,
                       "included": included, "excluded": excluded or [], "synthesis": SECRET,
                       "quality_report": {"note": SECRET}, "excel_dossier_storage_path": f"{user}/{run_id}/{name}"},
        }
        self.db.objects[f"{user}/{run_id}/{name}"] = b"xlsx-bytes"

    def report(self, run_id=RUN_A, preview=True, **extra):
        body = {"topic": "Ethical AI: Evaluation Frameworks", **extra}
        if run_id:
            body["research_run_id"] = run_id
        if preview:
            body["preview"] = True
        return self.client.post("/v1/reports", json=body, headers=AUTH)

    def named(self, name):
        return [e for e in self.events if e["event_name"] == name]


@pytest.fixture
def world(monkeypatch, tmp_path, fake_provider, synthesized_draft_json):
    return World(monkeypatch, tmp_path, fake_provider, synthesized_draft_json)


# --- the preview itself -------------------------------------------------------------------------------

def test_preview_keeps_totals_and_three_rows_per_list():
    result = {"query": "q", "status": "success", "included": sources(8), "excluded": sources(5, "Excluded")}
    view = exposure.preview_view(result)

    assert [s["uid"] for s in view["included"]] == ["Included-0", "Included-1", "Included-2"]
    assert len(view["excluded"]) == 3
    assert view["counts"] == {"included": 8, "excluded": 5, "reviewed": 13}
    assert view["locked"] == {"included_hidden": 5, "excluded_hidden": 2} and view["preview"] is True


def test_nothing_from_hidden_rows_or_unlisted_fields_survives_serialisation():
    result = {"query": "q", "included": sources(8), "excluded": sources(5, "Excluded"), "synthesis": SECRET,
              "quality_report": {"x": SECRET}, "apa_format_citation": SECRET, "brand_new_field": SECRET}
    text = json.dumps(exposure.preview_view(result))
    assert SECRET not in text, "hidden rows, abstracts, contributions and unlisted fields must not leak"
    assert set(exposure.preview_view(result)) <= set(exposure.RESULT_KEYS) | {"included", "excluded", "counts", "locked", "preview"}


def test_visible_rows_drop_abstracts_and_contributions_but_keep_the_audit_reason():
    row = exposure.preview_view({"included": sources(1), "excluded": []})["included"][0]
    assert "abstract" not in row and "source_contribution" not in row
    assert row["inclusion_reason"] == "Peer reviewed" and row["title"]


def test_free_downloads_are_reported_as_none_so_clients_never_promise_three():
    assert exposure.preview_view({"included": [], "excluded": []})["dossier_download"]["remaining"] == 0


def test_entitled_users_get_the_full_lists_plus_counts():
    full = exposure.results_for({"included": sources(8), "excluded": []}, entitled=True)
    assert len(full["included"]) == 8 and full["counts"]["reviewed"] == 8 and "preview" not in full


def test_a_short_list_has_nothing_locked():
    view = exposure.preview_view({"included": sources(2), "excluded": []})
    assert view["locked"] == {"included_hidden": 0, "excluded_hidden": 0} and len(view["included"]) == 2


# --- scan and run reads ------------------------------------------------------------------------------------

class BigPipeline:
    def run_research(self, **kwargs):
        Path(kwargs["output_directory"], "research_audit_x_20261001_120000.xlsx").write_bytes(b"workbook")
        return {"status": "success", "included": sources(8), "excluded": sources(5, "Excluded"),
                "synthesis": SECRET, "discovery_report_name": "research_audit_x_20261001_120000.xlsx"}


def scan(world, monkeypatch):
    monkeypatch.setattr(cloud_app, "pipeline", BigPipeline())
    return asyncio.run(cloud_app.execute_cloud_scan(cloud_app.ScanRequest(topic="AI evidence"), authorization="Bearer t"))


def test_a_free_scan_returns_a_preview_but_the_stored_run_stays_complete(world, monkeypatch):
    result = scan(world, monkeypatch)

    assert SECRET not in json.dumps(result) and len(result["included"]) == 3 and result["counts"]["reviewed"] == 13
    assert result["preview"] is True and result["research_run_id"]
    stored = world.db.runs[result["research_run_id"]]["result"]
    assert len(stored["included"]) == 8 and len(stored["excluded"]) == 5, "an upgrade must unlock the same run"
    assert world.named("snapshot_served")[0]["properties"]["surface"] == "results"


def test_a_paid_scan_is_complete(world, monkeypatch):
    world.paid = True
    result = scan(world, monkeypatch)
    assert len(result["included"]) == 8 and len(result["excluded"]) == 5 and result["counts"]["reviewed"] == 13
    assert "preview" not in result and not world.named("snapshot_served")


def test_reading_a_saved_run_applies_the_same_limit_and_upgrading_unlocks_it(world):
    world.seed_run(RUN_A, included=sources(8), excluded=sources(5, "Excluded"))

    free = world.client.get(f"/v1/research/{RUN_A}", headers=AUTH).json()["result"]
    assert len(free["included"]) == 3 and SECRET not in json.dumps(free) and "excel_dossier_storage_path" not in free

    world.paid = True
    paid = world.client.get(f"/v1/research/{RUN_A}", headers=AUTH).json()["result"]
    assert len(paid["included"]) == 8 and paid["counts"]["included"] == 8 and "excel_dossier_storage_path" not in paid


def test_another_users_run_is_not_readable(world):
    world.seed_run(OTHERS_RUN, user="someone-else")
    assert world.client.get(f"/v1/research/{OTHERS_RUN}", headers=AUTH).status_code == 404


def test_a_whitelisted_user_is_treated_as_paid(world, monkeypatch):
    monkeypatch.setattr(exposure.default_pricing_config, "whitelisted_emails", frozenset({"free@example.com"}), raising=False)
    world.seed_run(RUN_A, included=sources(8))
    assert len(world.client.get(f"/v1/research/{RUN_A}", headers=AUTH).json()["result"]["included"]) == 8


# --- Excel ------------------------------------------------------------------------------------------------------

def test_a_free_user_cannot_get_the_excel_dossier_and_nothing_is_read_or_counted(world):
    world.seed_run(RUN_A)
    response = world.client.get(f"/v1/research/{RUN_A}/dossier", headers=AUTH)

    assert response.status_code == 403 and response.json()["detail"]["error_code"] == "upgrade_required"
    assert world.db.reads == [] and world.db.claims == 0
    assert world.named("download_blocked")[0]["properties"]["surface"] == "excel"


def test_a_paid_user_gets_the_excel_dossier(world):
    world.paid = True
    world.seed_run(RUN_A)
    response = world.client.get(f"/v1/research/{RUN_A}/dossier", headers=AUTH)
    assert response.status_code == 200 and response.content == b"xlsx-bytes"


def test_free_excel_downloads_can_be_re_enabled_with_the_counter(world, monkeypatch):
    monkeypatch.setenv("NEXUS_FREE_DOSSIER_DOWNLOADS", "3")
    world.seed_run(RUN_A)
    assert world.client.get(f"/v1/research/{RUN_A}/dossier", headers=AUTH).status_code == 200
    assert world.db.claims == 1


# --- Word -----------------------------------------------------------------------------------------------------------

def test_a_free_report_without_preview_is_refused_before_any_model_call(world):
    world.seed_run(RUN_A)
    response = world.report(preview=False)
    assert response.status_code == 403 and response.json()["detail"]["error_code"] == "upgrade_required"
    assert world.provider.calls == 0


def test_the_old_client_shape_with_a_browser_source_list_gets_no_model_call_either(world):
    response = world.report(run_id=None, preview=False, included_sources=[dict(s) for s in SOURCES])
    assert response.status_code == 403 and world.provider.calls == 0


def test_a_preview_needs_a_saved_scan(world):
    response = world.report(run_id=None, preview=True, included_sources=[dict(s) for s in SOURCES])
    assert response.status_code == 403 and world.provider.calls == 0


def test_a_preview_returns_a_snapshot_and_never_a_document(world):
    world.seed_run(RUN_A)
    response = world.report()

    body = response.json()
    assert response.status_code == 200 and body["status"] == "snapshot"
    assert not {"document_base64", "download_url", "report_cache_id", "report_id", "document_name"} & set(body)
    snapshot = body["snapshot"]
    assert snapshot["opening_paragraph"] and snapshot["sections"] and snapshot["locked_sections"] >= 5
    assert world.provider.calls == 1
    assert world.named("snapshot_served")[-1]["properties"]["surface"] == "word"
    assert world.named("report_completed")[-1]["properties"]["tier"] == "free"


def test_the_full_document_is_cached_for_after_the_upgrade(world):
    world.seed_run(RUN_A)
    world.report()
    assert any(key.endswith("proposal-report.docx") for key in world.db.objects)


def test_re_opening_the_same_snapshot_costs_nothing_and_uses_no_credit(world):
    world.seed_run(RUN_A)
    first = world.report().json()
    second = world.report().json()
    assert second["status"] == "snapshot" and second["cache_hit"] is True and world.provider.calls == 1
    assert second["snapshot"] == first["snapshot"]


def test_the_monthly_credit_is_spent_once_and_a_second_scan_is_refused_without_a_model_call(world):
    world.seed_run(RUN_A)
    world.seed_run(RUN_B, included=SOURCES[:2])
    assert world.report(RUN_A).status_code == 200

    second = world.report(RUN_B)

    assert second.status_code == 403 and second.json()["detail"]["error_code"] == "upgrade_required"
    assert "preview" in second.json()["detail"]["message"].lower()
    assert world.provider.calls == 1


def test_a_failed_generation_gives_the_credit_back(world, monkeypatch):
    world.seed_run(RUN_A)
    real = cloud_app.generate_proposal_docx
    monkeypatch.setattr(cloud_app, "generate_proposal_docx", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("render exploded")))
    assert world.report().status_code == 500

    monkeypatch.setattr(cloud_app, "generate_proposal_docx", real)
    assert world.report().status_code == 200, "the failed attempt must not have used the month's preview"


def test_the_report_is_built_from_the_saved_run_not_from_the_browsers_list(world):
    world.seed_run(RUN_A)
    world.report(included_sources=[{"title": "Browser supplied", "authors": ["X"], "year": 2000}])
    assert [s["title"] for s in world.generated_with[0]] == [s["title"] for s in SOURCES]


def test_another_users_run_cannot_be_used_for_a_preview(world):
    world.seed_run(OTHERS_RUN, user="someone-else")
    assert world.report(OTHERS_RUN).status_code == 404 and world.provider.calls == 0


def test_a_free_user_cannot_download_a_cached_document_by_any_route(world):
    world.seed_run(RUN_A)
    world.report()
    key = next(k for k in world.db.objects if k.endswith("proposal-report.docx"))
    cache_id = cloud_app.report_cache_id(key)

    for path in (f"/v1/reports/cache/{cache_id}", f"/v1/reports/cache/{cache_id}?download=true",
                 f"/v1/reports/cache/{cache_id}/download", f"/api/reports/cache/{cache_id}/download"):
        response = world.client.get(path, headers=AUTH)
        assert response.status_code == 403 and response.json()["detail"]["error_code"] == "upgrade_required", path


def test_a_free_user_cannot_download_a_queued_report(world):
    from app.reports.report_queue import global_queue_manager
    job = global_queue_manager.enqueue(
        user_id="free-user", topic="t", report_type="proposal", domain="scholarly",
        included_sources=[], is_paid=False,
    ) if hasattr(global_queue_manager, "enqueue") else None
    if job is None:
        pytest.skip("queue manager has no enqueue")
    job.status, job.document_base64 = "ready", "AAAA"
    for path in (f"/v1/reports/{job.id}/download", f"/v1/reports/queue/{job.id}/download"):
        assert world.client.get(path, headers=AUTH).status_code == 403


def test_the_complete_literature_review_stays_paid_only(world):
    world.seed_run(RUN_A)
    response = world.report(preview=True, report_type="full_starter")
    assert response.status_code == 403 and world.provider.calls == 0


def test_buying_a_pack_returns_the_same_report_instantly_with_no_second_model_call(world):
    world.seed_run(RUN_A)
    assert world.report().json()["status"] == "snapshot"
    world.paid = True

    full = world.report(preview=False).json()

    assert full["status"] != "snapshot" and full["cache_hit"] is True and full["document_base64"]
    assert world.provider.calls == 1


def test_a_paid_report_from_a_saved_run_is_a_real_document_and_pays_no_credit(world):
    world.paid = True
    world.seed_run(RUN_A)
    body = world.report(preview=False).json()
    assert body["status"] == "ready" and body["document_base64"] and "snapshot" not in body
    assert world.named("report_completed")[-1]["properties"]["tier"] == "paid"


def test_an_expired_pack_stops_cached_documents_too(world):
    world.paid = True
    world.seed_run(RUN_A)
    world.report(preview=False)
    world.paid = False
    assert world.report(preview=False).status_code == 403


# --- the monthly credit counter ----------------------------------------------------------------------------------

def test_credits_are_honoured_released_and_reset_each_month(tmp_path, monkeypatch):
    store = EntitlementStore(str(tmp_path / "c.sqlite3"))
    assert store.claim_feature_use("u", "word_preview", 1) is True
    assert store.claim_feature_use("u", "word_preview", 1) is False
    store.release_feature_use("u", "word_preview")
    assert store.claim_feature_use("u", "word_preview", 1) is True
    assert store.claim_feature_use("other", "word_preview", 1) is True, "credits are per user"
    assert store.claim_feature_use("u", "other_feature", 1) is True, "and per feature"
    monkeypatch.setattr(EntitlementStore, "current_period_month", staticmethod(lambda: "2099-01"))
    assert store.claim_feature_use("u", "word_preview", 1) is True, "a new month starts fresh"


def test_a_zero_limit_grants_nothing(tmp_path):
    assert EntitlementStore(str(tmp_path / "z.sqlite3")).claim_feature_use("u", "word_preview", 0) is False


def test_a_release_never_goes_below_zero(tmp_path):
    store = EntitlementStore(str(tmp_path / "r.sqlite3"))
    store.release_feature_use("u", "word_preview")
    assert store.claim_feature_use("u", "word_preview", 1) is True
    assert store.claim_feature_use("u", "word_preview", 1) is False


class FakeSupabase:
    def __init__(self, result=1, error=None):
        self.calls, self.result, self.error = [], result, error

    def request(self, method, path, json=None, **kwargs):
        self.calls.append((method, path, json))
        if self.error:
            raise self.error
        return self.result


def test_supabase_claims_go_through_the_atomic_rpc(tmp_path):
    store = EntitlementStore(str(tmp_path / "s.sqlite3"))
    store.supabase = FakeSupabase(result=1)
    assert store.claim_feature_use("user-1", "word_preview", 1) is True
    method, path, payload = store.supabase.calls[0]
    assert (method, path) == ("POST", "rpc/nexus_claim_feature_use")
    assert payload["p_user_id"] == "user-1" and payload["p_feature"] == "word_preview" and payload["p_limit"] == 1
    store.supabase.result = -1
    assert store.claim_feature_use("user-1", "word_preview", 1) is False
    store.release_feature_use("user-1", "word_preview")
    assert store.supabase.calls[-1][1] == "rpc/nexus_release_feature_use"


def test_a_supabase_failure_denies_the_preview_instead_of_falling_back(world):
    world.seed_run(RUN_A)
    world.store.supabase = FakeSupabase(error=RuntimeError("down"))
    response = world.report()
    assert response.status_code == 503 and world.provider.calls == 0


def test_the_migration_defines_the_table_and_both_functions_for_the_service_role_only():
    sql = (Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "202610050001_user_feature_usage.sql").read_text(encoding="utf-8")
    for needle in ("user_feature_usage", "nexus_claim_feature_use", "nexus_release_feature_use",
                   "enable row level security", "to service_role", "from public, anon, authenticated"):
        assert needle in sql, needle


# --- snapshot extraction and events ------------------------------------------------------------------------------

def test_the_snapshot_describes_a_real_rendered_proposal(fake_provider, synthesized_draft_json):
    document = generate_proposal_docx("Ethical AI", "scholarly", [dict(s) for s in SOURCES],
                                      fake_provider(content=synthesized_draft_json()), None)
    snapshot = snapshot_from_docx(document.document_bytes)

    titles = [s["title"] for s in snapshot["sections"]]
    assert snapshot["title"] == "Ethical AI" and titles[0] == "Research Overview" and "References" in titles
    assert len(snapshot["opening_paragraph"].split()) >= 20 and len(snapshot["opening_paragraph"]) <= 701
    assert snapshot["locked_sections"] == len(titles) - 1
    assert snapshot["citation_count"] > 0 and snapshot["reference_count"] >= 1
    assert snapshot["total_words"] == sum(s["words"] for s in snapshot["sections"])


def test_the_snapshot_never_contains_the_rest_of_the_document(fake_provider, synthesized_draft_json):
    document = generate_proposal_docx("Ethical AI", "scholarly", [dict(s) for s in SOURCES],
                                      fake_provider(content=synthesized_draft_json()), None)
    text = json.dumps(snapshot_from_docx(document.document_bytes))
    assert len(text) < 3000, "outline, counts and one paragraph only"


def test_the_new_events_are_registered_and_valid():
    assert schema.validate("snapshot_served", {"surface": "word", "locked_sections": 8}, schema.SERVER) == []
    assert schema.validate("download_blocked", {"surface": "excel"}, schema.SERVER) == []
    assert "bad_type:surface" in schema.validate("download_blocked", {"surface": "elsewhere"}, schema.SERVER)


# --- metrics ---------------------------------------------------------------------------------------------------------

def test_snapshot_to_purchase_counts_users_who_saw_a_preview_and_then_bought():
    from tests.test_metrics_catalog import measure, row
    rows = [row("snapshot_served", user="a", surface="word"), row("snapshot_served", user="b", surface="results"),
            row("snapshot_served", user="c", surface="results"), row("bundle_purchased", user="a", price=10.0),
            row("bundle_purchased", user="z", price=10.0)]
    result = measure(rows, "snapshot_to_purchase")
    assert (result["value"], result["numerator"], result["denominator"]) == (pytest.approx(1 / 3), 1, 3)
    assert result["breakdown"]["users_by_surface"] == {"word": 1, "results": 2}


def test_preview_cost_per_purchase_prices_only_uncached_free_previews(monkeypatch):
    from tests.test_metrics_catalog import measure, row
    monkeypatch.setenv("LLM_PRICES_JSON", json.dumps({"priced": {"input": 1.0, "output": 5.0}}))
    rows = [row("report_completed", tier="free", cache_hit=False, request_id="rep-free0001"),
            row("llm_call", model="priced", input_tokens=1_000_000, output_tokens=200_000, request_id="rep-free0001"),
            row("report_completed", tier="free", cache_hit=True, request_id="rep-free0002"),
            row("report_completed", tier="paid", cache_hit=False, request_id="rep-paid0001"),
            row("llm_call", model="priced", input_tokens=5_000_000, output_tokens=0, request_id="rep-paid0001"),
            row("bundle_purchased", user="a", price=10.0), row("bundle_purchased", user="b", price=19.0)]
    result = measure(rows, "preview_cost_per_purchase")

    assert result["value"] == pytest.approx(1.0), "$2.00 of free-preview spend over two purchases"
    assert result["breakdown"]["preview_spend_usd"] == pytest.approx(2.0) and result["breakdown"]["revenue"] == 29.0
    assert result["breakdown"]["free_previews"] == 1


def test_preview_cost_reports_no_data_when_nothing_was_bought_or_previewed():
    from tests.test_metrics_catalog import measure, row
    assert measure([], "preview_cost_per_purchase")["value"] is None
    assert measure([row("bundle_purchased", price=10.0)], "preview_cost_per_purchase")["value"] is None


# --- the clients ---------------------------------------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
WEBSITE_JS = (ROOT / "website" / "app.js").read_text(encoding="utf-8")
EXTENSION_JS = (ROOT / "extension" / "popup.js").read_text(encoding="utf-8")


def test_the_website_takes_totals_from_the_server_and_shows_a_locked_row():
    assert "Number(data.counts?.included ?? resultIncludedSources.length)" in WEBSITE_JS
    body = WEBSITE_JS[WEBSITE_JS.index("function lockedRow("):]
    body = body[:body.index("\n    }\n")]
    assert "textContent" in body and "innerHTML" not in body and "button-cta" in body
    assert "hidden > 0 ? [lockedRow(hidden, included)] : []" in WEBSITE_JS


def test_the_website_asks_the_server_to_build_reports_from_the_saved_run():
    assert "research_run_id: activeResult.research_run_id" in WEBSITE_JS


def test_upgrade_required_is_an_offer_not_an_error_on_the_website():
    assert "errorDetail.error_code === 'upgrade_required'" in WEBSITE_JS
    assert "error.payload?.detail?.error_code === 'upgrade_required'" in WEBSITE_JS
    assert "of 3 free downloads" not in WEBSITE_JS


def test_the_extension_uses_server_totals_and_never_replays_a_cached_preview():
    assert "data.counts?.included" in EXTENSION_JS and "research_run_id: activeResearchRunId" in EXTENSION_JS
    assert "!cached.research_cache_result.preview" in EXTENSION_JS
    assert "errorCode === 'upgrade_required'" in EXTENSION_JS
    assert "typeof error.detail === 'string' ? error.detail : (error.detail?.message || message)" in EXTENSION_JS
