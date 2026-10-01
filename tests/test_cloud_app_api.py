import asyncio
import base64

import pytest
from fastapi import HTTPException

import cloud_app


def test_cloud_scan_passes_options_and_persists_result(monkeypatch):
    class Pipeline:
        def run_research(self, **kwargs):
            self.kwargs = kwargs
            return {"status": "success", "included": [{"title": "Evidence"}], "excluded": []}

    class Database:
        def insert(self, table, values):
            self.table = table
            self.values = values
            return {"id": "run-id"}

    pipeline = Pipeline()
    database = Database()
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app, "require_supabase_database", lambda: database)
    monkeypatch.setattr(cloud_app, "pipeline", pipeline)

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
    assert pipeline.kwargs["additional_sources"][0]["abstract"] == "Research notes"
    assert database.table == "research_runs"
    assert database.values["user_id"] == "user-id"
    assert result["research_run_id"] == "run-id"


def test_cloud_scan_rejects_more_than_free_source_limit_for_free_users(monkeypatch):
    monkeypatch.setattr(cloud_app, "require_supabase_user", lambda authorization: {"id": "user-id"})
    monkeypatch.setattr(cloud_app, "require_api_access", lambda key: None)
    monkeypatch.setattr(cloud_app.entitlements, "is_active", lambda user_id: False)

    with pytest.raises(HTTPException) as error:
        asyncio.run(cloud_app.execute_cloud_scan(
            cloud_app.ScanRequest(topic="AI evidence", max_sources=21),
            authorization="Bearer token",
        ))

    assert error.value.status_code == 403


def test_uploaded_source_rejects_invalid_base64():
    with pytest.raises(HTTPException) as error:
        cloud_app.parse_uploaded_sources(
            [{"name": "invalid.pdf", "data": "not-base64"}],
            "scholarly",
        )

    assert error.value.status_code == 400
