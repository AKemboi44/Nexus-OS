import asyncio
import base64
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import HTTPException

import cloud_app

@pytest.fixture(autouse=True)
def clean_entitlements_and_pricing(tmp_path, monkeypatch):
    import app.payments.entitlements
    db_path = str(tmp_path / "test_api_entitlements.sqlite3")
    store = app.payments.entitlements.EntitlementStore(database_path=db_path)
    monkeypatch.setattr(cloud_app, "entitlements", store)
    yield


def test_cloud_scan_passes_options_and_persists_result(monkeypatch):
    class Pipeline:
        def run_research(self, **kwargs):
            self.kwargs = kwargs
            Path(kwargs["output_directory"], "research_audit_ai_evidence_20261001_120000.xlsx").write_bytes(
                b"workbook"
            )
            return {
                "status": "success",
                "included": [{"title": "Evidence"}],
                "excluded": [],
                "discovery_report_name": "research_audit_ai_evidence_20261001_120000.xlsx",
            }

    class Database:
        def __init__(self):
            self.inserted = []

        def request(self, method, resource, **kwargs):
            assert (method, resource) == ("GET", "dossier_download_usage")
            return []

        def upload_storage_object(self, bucket, path, content, content_type):
            self.upload = (bucket, path, content, content_type)

        def insert(self, table, values):
            self.inserted.append((table, values))
            return {"id": values.get("id", "saved-dossier-id")}

    pipeline = Pipeline()
    database = Database()
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: database)
    monkeypatch.setattr(cloud_app, "pipeline", pipeline)
    monkeypatch.setattr(cloud_app.entitlements, "is_active", lambda user_id: False)

    result = asyncio.run(cloud_app.execute_cloud_scan(
        cloud_app.ScanRequest(
            topic="AI evidence",
            max_sources=5,
            uploaded_sources=[{
                "name": "notes.txt",
                "data": base64.b64encode(b"Research notes").decode("ascii"),
            }],
            selected_inclusion_reasons=["Peer-reviewed or journal-associated source"],
        ),
        authorization="Bearer token",
    ))

    assert pipeline.kwargs["query"] == "AI evidence"
    assert pipeline.kwargs["output_directory"]
    assert pipeline.kwargs["additional_sources"][0]["abstract"] == "Research notes"
    assert [table for table, _ in database.inserted] == ["research_runs", "saved_dossiers"]
    run_values = database.inserted[0][1]
    saved_dossier_values = database.inserted[1][1]
    assert run_values["user_id"] == "user-id"
    assert result["research_run_id"] == run_values["id"]
    assert result["saved_dossier_id"] == "saved-dossier-id"
    assert run_values["result"]["excel_dossier_storage_path"] == database.upload[1]
    assert saved_dossier_values["payload"]["research_run_id"] == result["research_run_id"]
    assert saved_dossier_values["payload"]["query"] == "AI evidence"
    assert saved_dossier_values["payload"]["status"] == "success"
    assert saved_dossier_values["payload"]["discovery_report_name"] == "research_audit_ai_evidence_20261001_120000.xlsx"
    assert saved_dossier_values["payload"]["included_count"] == 1
    assert saved_dossier_values["payload"]["excluded_count"] == 0
    assert saved_dossier_values["payload"]["ab_variant"] in ("variant_a", "variant_b")
    assert database.upload[0] == cloud_app.DOSSIER_STORAGE_BUCKET
    assert database.upload[2] == b"workbook"
    assert "excel_dossier_base64" not in run_values["result"]
    assert result["discovery_report_directory"] is None
    assert "excel_dossier_storage_path" not in result
    assert result["dossier_download"]["remaining"] == 3


def test_cloud_scan_preserves_the_complete_topic_at_pipeline_boundary(monkeypatch):
    class Pipeline:
        def run_research(self, **kwargs):
            self.query = kwargs["query"]
            Path(kwargs["output_directory"], "scan.xlsx").write_bytes(b"workbook")
            return {
                "status": "success", "query": self.query, "included": [], "excluded": [],
                "discovery_report_name": "scan.xlsx",
            }

    class Database:
        def request(self, *args, **kwargs):
            return []

        def upload_storage_object(self, *args):
            return None

        def insert(self, table, values):
            return {"id": values.get("id", "saved-dossier-id")}

    pipeline = Pipeline()
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: Database())
    monkeypatch.setattr(cloud_app, "pipeline", pipeline)
    monkeypatch.setattr(cloud_app.entitlements, "is_active", lambda user_id: False)

    result = asyncio.run(cloud_app.execute_cloud_scan(
        cloud_app.ScanRequest(topic="Token optimization", max_sources=1),
        authorization="Bearer token",
    ))

    assert pipeline.query == "Token optimization"
    assert result["query"] == "Token optimization"


def test_scan_records_privacy_preserving_operational_events(monkeypatch):
    class Pipeline:
        def run_research(self, **kwargs):
            Path(kwargs["output_directory"], "scan.xlsx").write_bytes(b"workbook")
            return {
                "status": "success",
                "included": [{"title": "Evidence", "authors": ["Author"], "year": 2024, "venue": "Journal"}],
                "excluded": [{"title": "Unusable"}],
                "discovery_report_name": "scan.xlsx",
            }

    class Database:
        def request(self, method, resource, **kwargs):
            return []

        def upload_storage_object(self, *args):
            return None

        def insert(self, table, values):
            return {"id": values.get("id", "saved-dossier-id")}

    events = []
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: Database())
    monkeypatch.setattr(cloud_app, "pipeline", Pipeline())
    monkeypatch.setattr(cloud_app.entitlements, "is_active", lambda user_id: False)
    monkeypatch.setattr(cloud_app.analytics, "record", lambda **event: events.append(event))

    asyncio.run(cloud_app.execute_cloud_scan(
        cloud_app.ScanRequest(topic="Sensitive research prompt", max_sources=3),
        authorization="******",
    ))

    assert "scan_started" in [event["event_name"] for event in events]
    assert "scan_completed" in [event["event_name"] for event in events]
    assert "excel_export_completed" in [event["event_name"] for event in events]
    completed_event = [event for event in events if event["event_name"] == "scan_completed"][0]
    completed = completed_event["properties"]
    assert completed["requested_count"] == 3
    assert completed["reviewed_count"] == 2
    assert completed["metadata_complete_count"] == 1
    assert "topic" not in completed
    assert "Sensitive research prompt" not in str(events)


def test_analytics_recording_failure_does_not_break_cached_report(monkeypatch):
    class Database:
        def download_storage_object(self, bucket, path):
            return b"cached docx"

    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: Database())
    monkeypatch.setattr(cloud_app.analytics, "record", lambda **event: (_ for _ in ()).throw(RuntimeError("offline")))

    result = asyncio.run(cloud_app.generate_research_report(
        cloud_app.ReportRequest(
            topic="Sensitive report prompt",
            included_sources=[{
                "title": "Evidence", "authors": ["Author"], "year": 2024, "venue": "Journal",
            }],
        ),
        authorization="******",
    ))

    assert result["cache_hit"] is True


def test_provider_quota_error_enqueues_pending_report(monkeypatch):
    class Database:
        def __init__(self):
            self.uploads = []

        def download_storage_object(self, bucket, path):
            raise cloud_app.SupabaseRequestError(404, "not found")

        def upload_storage_object(self, *args):
            self.uploads.append(args)

    class DossierGenerator:
        def generate_comprehensive_dossier(self, **kwargs):
            raise cloud_app.ReportProviderLimitError("429 RESOURCE_EXHAUSTED quota exceeded")

    database = Database()
    events = []
    cloud_app.global_queue_manager.clear()
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id", "email": "test@example.com"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: database)
    monkeypatch.setattr(cloud_app.analytics, "record", lambda **event: events.append(event))
    monkeypatch.setattr(cloud_app.entitlements, "is_active", lambda user_id: True)
    import app.reports.dossier_generator
    monkeypatch.setattr(app.reports.dossier_generator, "DossierGenerator", DossierGenerator)

    result = asyncio.run(cloud_app.generate_research_report(
        cloud_app.ReportRequest(
            topic="Quota-safe report",
            report_type="full_starter",
            included_sources=[{
                "title": "Evidence", "authors": ["Author"], "year": 2024, "venue": "Journal",
            }],
        ),
        authorization="******",
    ))

    assert result["status"] == "queued"
    assert result["action"] == "report_queued_pending"
    assert result["estimated_wait"] == "usually under 20 minutes"
    assert "job_id" in result
    assert "document_base64" not in result
    assert database.uploads == []
    assert events[-1]["event_name"] == "report_queued"
    assert events[-1]["properties"]["estimated_wait"] == "usually under 20 minutes"
    
    # Check queue manager has the job
    job = cloud_app.global_queue_manager.get_job(result["job_id"])
    assert job is not None
    assert job.status == "queued"
    assert job.topic == "Quota-safe report"
    assert job.user_id == "user-id"


def test_dossier_download_is_owner_scoped_and_claims_free_allowance(monkeypatch):
    run_id = UUID("c843eafe-7bd6-4ba1-92f9-d592d16fcd91")
    filename = "research_audit_ai_20261001_120000.xlsx"
    path = f"user-id/{run_id}/{filename}"

    class Database:
        def request(self, method, resource, **kwargs):
            self.query = kwargs["params"]
            return [{
                "result": {
                    "discovery_report_name": filename,
                    "excel_dossier_storage_path": path,
                }
            }]

        def download_storage_object(self, bucket, object_path):
            self.download = (bucket, object_path)
            return b"excel bytes"

    database = Database()
    original_request = database.request

    def request(method, resource, **kwargs):
        if resource == "rpc/nexus_claim_dossier_download":
            database.claim = kwargs["json"]
            return 2
        return original_request(method, resource, **kwargs)

    database.request = request
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: database)
    monkeypatch.setattr(cloud_app.entitlements, "is_active", lambda user_id: False)

    response = asyncio.run(cloud_app.download_research_dossier(run_id, authorization="Bearer token"))

    assert response.body == b"excel bytes"
    assert response.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.headers["x-dossier-downloads-remaining"] == "2"
    assert database.query["user_id"] == "eq.user-id"
    assert database.claim == {"p_user_id": "user-id"}
    assert database.download == (cloud_app.DOSSIER_STORAGE_BUCKET, path)


def test_dossier_download_whitelist_bypasses_quota(monkeypatch):
    run_id = UUID("c843eafe-7bd6-4ba1-92f9-d592d16fcd91")
    filename = "research_audit_ai_20261001_120000.xlsx"
    result = {
        "discovery_report_name": filename,
        "excel_dossier_storage_path": f"user-id/{run_id}/{filename}",
    }

    class Database:
        def request(self, method, resource, **kwargs):
            assert resource == "research_runs"
            return [{"result": result}]

        def download_storage_object(self, bucket, path):
            return b"excel bytes"

    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {
        "id": "user-id", "email": "AkIpToO20@GmAiL.cOm",
    })
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(
        cloud_app.entitlements,
        "is_active",
        lambda user_id: pytest.fail("Whitelisted users should not need an entitlement lookup."),
    )
    database = Database()
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: database)

    response = asyncio.run(cloud_app.download_research_dossier(run_id, authorization="Bearer token"))

    assert response.body == b"excel bytes"
    assert response.headers["x-dossier-downloads-remaining"] == "unlimited"


def test_dossier_download_rejects_exhausted_free_allowance(monkeypatch):
    run_id = UUID("c843eafe-7bd6-4ba1-92f9-d592d16fcd91")
    filename = "research_audit_ai_20261001_120000.xlsx"
    path = f"user-id/{run_id}/{filename}"

    class Database:
        def request(self, method, resource, **kwargs):
            if resource == "rpc/nexus_claim_dossier_download":
                return -1
            return [{"result": {
                "discovery_report_name": filename,
                "excel_dossier_storage_path": path,
            }}]

        def download_storage_object(self, bucket, object_path):
            return b"excel bytes"

    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", Database)
    monkeypatch.setattr(cloud_app.entitlements, "is_active", lambda user_id: False)

    with pytest.raises(HTTPException) as error:
        asyncio.run(cloud_app.download_research_dossier(run_id, authorization="Bearer token"))

    assert error.value.status_code == 403
    assert "all 3 free" in error.value.detail


def test_dossier_download_paid_user_bypasses_quota(monkeypatch):
    run_id = UUID("c843eafe-7bd6-4ba1-92f9-d592d16fcd91")
    filename = "research_audit_ai_20261001_120000.xlsx"
    path = f"user-id/{run_id}/{filename}"

    class Database:
        def request(self, method, resource, **kwargs):
            assert resource == "research_runs"
            return [{"result": {
                "discovery_report_name": filename,
                "excel_dossier_storage_path": path,
            }}]

        def download_storage_object(self, bucket, object_path):
            return b"excel bytes"

    database = Database()
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {
        "id": "user-id", "email": "paid@example.com",
    })
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: database)
    monkeypatch.setattr(cloud_app.entitlements, "is_active", lambda user_id: True)

    response = asyncio.run(cloud_app.download_research_dossier(run_id, authorization="Bearer token"))

    assert response.body == b"excel bytes"
    assert response.headers["x-dossier-downloads-remaining"] == "unlimited"


def test_cloud_scan_rejects_more_than_free_source_limit_for_free_users(monkeypatch):
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app.entitlements, "is_active", lambda user_id: False)
    # Simulate user has already used their 1 free query
    cloud_app.entitlements.increment_query_usage("user-id")

    with pytest.raises(HTTPException) as error:
        asyncio.run(cloud_app.execute_cloud_scan(
            cloud_app.ScanRequest(topic="AI evidence", max_sources=10),
            authorization="Bearer token",
        ))

    assert error.value.status_code == 403
    assert error.value.detail["requires_bundle"] is True


def test_word_report_failure_is_logged_with_original_exception(monkeypatch, caplog):
    from app.reports.dossier_generator import DossierGenerator

    class Database:
        def download_storage_object(self, bucket, path):
            raise cloud_app.SupabaseRequestError(404, "Object not found")

    def fail_generation(self, **kwargs):
        raise RuntimeError("editorial service unavailable")

    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: Database())
    monkeypatch.setattr(
        DossierGenerator,
        "generate_comprehensive_dossier",
        fail_generation,
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(cloud_app.generate_research_report(
            cloud_app.ReportRequest(
                topic="Research quality",
                report_type="full_starter",
                included_sources=[{
                    "title": "Evidence",
                    "authors": ["Author"],
                    "year": 2024,
                    "venue": "Journal of Evidence",
                }],
            ),
            authorization="******",
        ))

    assert error.value.status_code == 500
    assert "editorial service unavailable" in str(error.value.detail)


def test_word_report_returns_cached_document_without_regenerating(monkeypatch):
    class Database:
        def download_storage_object(self, bucket, path):
            self.bucket = bucket
            self.path = path
            return b"cached docx"

    database = Database()
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: database)

    result = asyncio.run(cloud_app.generate_research_report(
        cloud_app.ReportRequest(
            topic="Research quality",
            included_sources=[{
                "title": "Evidence",
                "authors": ["Author"],
                "year": 2024,
                "venue": "Journal of Evidence",
            }],
        ),
        authorization="******",
    ))

    assert result["action"] == "cached_docx_download"
    assert result["cache_hit"] is True
    assert base64.b64decode(result["document_base64"]) == b"cached docx"
    assert database.bucket == cloud_app.DOSSIER_STORAGE_BUCKET
    assert database.path.startswith("user-id/report-cache/")


def test_cached_word_report_download_is_user_scoped(monkeypatch):
    cache_digest = "a" * 64
    cache_id = f"v{cloud_app.REPORT_CACHE_VERSION}-{cache_digest}"

    class Database:
        def download_storage_object(self, bucket, path):
            self.bucket = bucket
            self.path = path
            return b"cached docx"

    database = Database()
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: database)

    result = asyncio.run(cloud_app.download_cached_research_report(
        cache_id,
        authorization="******",
    ))

    assert result["cache_hit"] is True
    assert result["report_cache_id"] == cache_id
    assert base64.b64decode(result["document_base64"]) == b"cached docx"
    assert database.bucket == cloud_app.DOSSIER_STORAGE_BUCKET
    assert database.path == f"user-id/report-cache/{cache_digest}/proposal-report.docx"


def test_cached_word_report_download_rejects_outdated_cache_versions(monkeypatch):
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)

    with pytest.raises(HTTPException) as error:
        asyncio.run(cloud_app.download_cached_research_report(
            "a" * 64,
            authorization="******",
        ))

    assert error.value.status_code == 410
    assert "outdated" in error.value.detail


def test_word_report_rejects_sources_without_citable_metadata(monkeypatch):
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)

    with pytest.raises(HTTPException) as error:
        asyncio.run(cloud_app.generate_research_report(
            cloud_app.ReportRequest(
                topic="Research quality",
                included_sources=[{
                    "title": "Evidence",
                    "authors": ["Unknown Contributor"],
                    "year": 2024,
                }],
            ),
            authorization="******",
        ))

    assert error.value.status_code == 422
    assert "publication metadata" in error.value.detail


def test_uploaded_source_rejects_invalid_base64():
    with pytest.raises(HTTPException) as error:
        cloud_app.parse_uploaded_sources(
            [{"name": "invalid.pdf", "data": "not-base64"}],
            "scholarly",
        )

    assert error.value.status_code == 400
