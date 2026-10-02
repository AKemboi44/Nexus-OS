# cloud_app.py - Block 1 of 2
import os
import sys
import secrets
import logging
import requests
import base64
import hashlib
import json
import re
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4
from urllib.parse import quote
from fastapi import FastAPI, HTTPException, Header, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, constr
from typing import Optional, List, Dict, Any
from app.supabase_store import SupabaseRequestError, SupabaseRestClient
from app.research.research_pipeline import ResearchPipeline
from app.analytics.event_store import AnalyticsEventStore
from app.payments.paypal import PayPalClient
from app.payments.entitlements import EntitlementStore
from app.synthesis.citation_engine import CitationEngine
from app.agents.scribe_agent import ReportSynthesisError

app = FastAPI(title="Nexus Research AI Gateway", version="1.0.0")
logger = logging.getLogger(__name__)
allowed_origins = os.getenv("NEXUS_ALLOWED_ORIGINS", os.getenv("CORS_origins", "*"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-Dossier-Downloads-Remaining"],
)
pipeline = ResearchPipeline()
analytics = AnalyticsEventStore()
paypal = PayPalClient()
entitlements = EntitlementStore()
supabase_database = SupabaseRestClient.from_env()

class ScanRequest(BaseModel):
    topic: str
    max_sources: Optional[int] = 5
    domain: Optional[str] = "scholarly"
    uploaded_sources: List[Dict[str, Any]] = Field(default_factory=list)
    selected_inclusion_reasons: List[str] = Field(default_factory=list)

class AnalyticsEvent(BaseModel):
    user_id: Optional[str] = "anonymous"
    session_id: Optional[str] = "unknown"
    event: str
    timestamp: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class PayPalOrderRequest(BaseModel):
    plan: str = "pro"
    user_id: str = "anonymous"


class PayPalCaptureRequest(BaseModel):
    order_id: str
    user_id: str = "anonymous"

class SavedDossierRequest(BaseModel):
    title: constr(min_length=1, max_length=200)
    payload: Dict[str, Any]


class SavedSourceRequest(BaseModel):
    source: Dict[str, Any]


class ReportRequest(BaseModel):
    topic: str
    included_sources: List[Dict[str, Any]] = Field(default_factory=list)
    uploaded_sources: List[Dict[str, Any]] = Field(default_factory=list)
    report_type: str = "proposal"
    domain: str = "scholarly"
    max_sources: int = 5


def require_admin(x_admin_token: Optional[str]):
    configured = os.getenv("NEXUS_ADMIN_TOKEN")
    if not configured or not x_admin_token or not secrets.compare_digest(x_admin_token, configured):
        raise HTTPException(status_code=401, detail="Admin authentication required.")


def require_api_access(x_api_key: Optional[str]):
    configured = os.getenv("NEXUS_API_KEY")
    if configured and x_api_key != configured:
        raise HTTPException(status_code=401, detail="API authentication required.")


def require_supabase_user(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="A valid Supabase access token is required.")

    supabase_url = os.getenv("SUPABASE_URL")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_role_key:
        raise HTTPException(status_code=503, detail="Supabase authentication is not configured.")

    try:
        response = requests.get(
            f"{supabase_url.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": service_role_key,
                "Authorization": authorization,
            },
            timeout=5,
        )
    except requests.RequestException as error:
        raise HTTPException(status_code=503, detail="Supabase authentication service is unavailable.") from error

    if response.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Supabase access token is invalid or expired.")
    if not response.ok:
        raise HTTPException(status_code=503, detail="Could not validate the Supabase access token.")

    try:
        user = response.json()
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Supabase returned an invalid authentication response.") from error
    if not isinstance(user, dict) or not user.get("id"):
        raise HTTPException(status_code=401, detail="Supabase access token did not identify a user.")
    return user


def supabase_user_id(user: Dict[str, Any]) -> str:
    return str(user["id"])


def require_supabase_database() -> SupabaseRestClient:
    if not supabase_database:
        raise HTTPException(status_code=503, detail="Supabase database is not configured.")
    return supabase_database


DOSSIER_DOWNLOAD_LIMIT = 3
DOSSIER_DOWNLOAD_WHITELIST = {"akiptoo20@gmail.com"}
DOSSIER_STORAGE_BUCKET = "research-dossiers"
REPORT_CACHE_VERSION = "7"
REPORT_CACHE_PREFIX = "report-cache"
DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def report_cache_id(cache_key: str) -> str:
    return f"v{REPORT_CACHE_VERSION}-{Path(cache_key).parent.name}"


def parse_report_cache_id(cache_id: str) -> Optional[str]:
    match = re.fullmatch(
        rf"v{re.escape(REPORT_CACHE_VERSION)}-([a-f0-9]{{64}})",
        str(cache_id or ""),
    )
    return match.group(1) if match else None


def record_backend_analytics(
    event_name: str,
    user_id: str,
    properties: Dict[str, Any],
) -> None:
    """Persist only aggregate backend telemetry without affecting the request."""
    try:
        analytics.record(
            event_name=event_name,
            user_id=user_id,
            session_id="backend",
            properties=properties,
        )
    except Exception:
        logger.exception("Could not persist backend analytics event %s.", event_name)


def elapsed_milliseconds(started_at: float) -> int:
    return max(0, int((time.monotonic() - started_at) * 1000))


def normalized_error_category(error: Exception) -> str:
    if isinstance(error, ReportSynthesisError):
        return "quality_or_provider"
    if isinstance(error, HTTPException):
        return "client_request" if 400 <= error.status_code < 500 else "service_unavailable"
    if isinstance(error, (SupabaseRequestError, RuntimeError)):
        return "dependency_failure"
    return "internal_error"


def privacy_safe_analytics_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Reject free-form content before it can reach the durable telemetry store."""
    allowed_string_keys = {
        "provider", "plan", "payment_type", "status", "event_type", "error_code",
        "error_category", "domain_category", "report_type", "provider_selected",
        "model_selected", "outcome_category",
    }
    sensitive_keys = {
        "topic", "prompt", "query", "source", "sources", "title", "abstract",
        "text", "content", "message", "detail", "description",
    }
    safe_context = {}
    for key, value in context.items():
        normalized_key = str(key).strip().lower()
        if (
            normalized_key in sensitive_keys
            or any(part in normalized_key for part in ("prompt", "topic", "source", "content"))
            or isinstance(value, (dict, list))
        ):
            raise ValueError("Telemetry context may only contain non-sensitive counters, IDs, and categories.")
        if isinstance(value, str) and (
            normalized_key not in allowed_string_keys
            and not normalized_key.endswith(("_id", "_hash"))
        ):
            raise ValueError("Telemetry context may only contain non-sensitive counters, IDs, and categories.")
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError("Telemetry context may only contain non-sensitive counters, IDs, and categories.")
        safe_context[normalized_key[:80]] = value
    return safe_context


def source_metadata_metrics(sources: Any) -> Dict[str, int]:
    if not isinstance(sources, list):
        return {"reviewed_count": 0, "metadata_complete_count": 0}
    complete_count = sum(
        isinstance(source, dict)
        and bool(source.get("title"))
        and bool(source.get("authors"))
        and bool(source.get("year"))
        and bool(source.get("venue") or source.get("doi") or source.get("url"))
        for source in sources
    )
    return {
        "reviewed_count": len(sources),
        "metadata_complete_count": complete_count,
    }


def scribe_telemetry(scribe: Any) -> Dict[str, Any]:
    """Extract non-content report signals exposed by the report generator."""
    attempts = getattr(scribe, "telemetry_attempts", None)
    telemetry = {
        "provider_selected": str(getattr(scribe, "provider", "unknown") or "unknown")[:40],
        "model_selected": str(getattr(scribe, "model", "unknown") or "unknown")[:120],
        "provider_attempt_count": (
            min(max(attempts, 0), 10) if type(attempts) is int else None
        ),
        "provider_fallback_used": bool(getattr(scribe, "telemetry_fallback_used", False)),
        "validation_correction_used": bool(getattr(scribe, "telemetry_correction_used", False)),
        "degraded_mode": bool(getattr(scribe, "fallback_mode", None)),
    }
    try:
        telemetry["configured_output_token_limit"] = min(
            max(int(scribe._proposal_output_token_limit()), 1), 4096
        )
    except (AttributeError, TypeError, ValueError):
        pass
    return telemetry


def is_dossier_download_unlimited(user: Dict[str, Any]) -> bool:
    return (
        str(user.get("email") or "").strip().lower() in DOSSIER_DOWNLOAD_WHITELIST
        or entitlements.is_active(supabase_user_id(user))
    )


def dossier_download_status(user: Dict[str, Any]) -> Dict[str, Any]:
    if is_dossier_download_unlimited(user):
        return {"unlimited": True, "limit": None, "used": 0, "remaining": None}
    records = require_supabase_database().request(
        "GET",
        "dossier_download_usage",
        params={
            "user_id": f"eq.{supabase_user_id(user)}",
            "select": "download_count",
            "limit": 1,
        },
    )
    used = int(records[0]["download_count"]) if records else 0
    return {
        "unlimited": False,
        "limit": DOSSIER_DOWNLOAD_LIMIT,
        "used": used,
        "remaining": max(0, DOSSIER_DOWNLOAD_LIMIT - used),
    }


def report_cache_key(
    user: Dict[str, Any],
    topic: str,
    report_type: str,
    domain: str,
    included_sources: List[Dict[str, Any]],
) -> str:
    cache_input = {
        "version": REPORT_CACHE_VERSION,
        "topic": topic,
        "report_type": report_type,
        "domain": domain,
        "included_sources": included_sources,
    }
    serialized_input = json.dumps(
        jsonable_encoder(cache_input),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    digest = hashlib.sha256(serialized_input.encode("utf-8")).hexdigest()
    return (
        f"{supabase_user_id(user)}/{REPORT_CACHE_PREFIX}/{digest}/"
        f"{report_type}-report.docx"
    )


def cached_report_response(
    document_bytes: bytes,
    cache_key: str,
    report_type: str,
) -> Dict[str, Any]:
    return {
        "status": "success",
        "action": "cached_docx_download",
        "generation_mode": "ai_synthesized",
        "degraded": False,
        "document_name": Path(cache_key).name,
        "document_base64": base64.b64encode(document_bytes).decode("ascii"),
        "report_type": report_type,
        "cache_hit": True,
        "report_cache_id": report_cache_id(cache_key),
        "report_cache_version": REPORT_CACHE_VERSION,
    }


def parse_uploaded_sources(uploads: List[Dict[str, Any]], domain: str) -> List[Dict[str, Any]]:
    if len(uploads) > 10:
        raise HTTPException(status_code=400, detail="A request can include at most 10 uploaded sources.")
    parsed = []
    total_size = 0
    for upload in uploads:
        name = str(upload.get("name", "uploaded-document"))[:255]
        encoded = upload.get("data", "")
        if not isinstance(encoded, str) or len(encoded) > 20_000_000:
            raise HTTPException(status_code=400, detail=f"Upload {name} is invalid or exceeds the 15 MB limit.")
        try:
            raw_data = base64.b64decode(encoded, validate=True)
            if not raw_data:
                raise ValueError("Upload is empty.")
            total_size += len(raw_data)
            if total_size > 15_000_000:
                raise HTTPException(status_code=400, detail="Combined uploads cannot exceed 15 MB.")
            if name.lower().endswith(".pdf") or upload.get("type") == "application/pdf":
                import pymupdf
                with pymupdf.open(stream=raw_data, filetype="pdf") as pdf:
                    text = "\n".join(page.get_text() for page in pdf).strip()
            else:
                text = raw_data.decode("utf-8", errors="replace").strip()
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(status_code=400, detail=f"Could not read uploaded source {name}.") from error
        parsed.append({
            "uid": f"upload_{name}",
            "title": name,
            "authors": ["User Upload"],
            "venue": "User-provided source",
            "year": "n.d.",
            "citation_count": 0,
            "is_peer_reviewed": False,
            "abstract": text[:12000] or "No extractable text.",
            "url": f"file:///{name}",
            "domain": domain,
            "provider_source": "user_upload",
            "include": bool(text.strip()),
        })
    return parsed


# cloud_app.py - Block 2 of 2
@app.post("/v1/scan")
async def execute_cloud_scan(
    payload: ScanRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    if not payload.topic.strip():
        raise HTTPException(status_code=400, detail="Topic cannot be blank.")
    if not 1 <= (payload.max_sources or 0) <= 100:
        raise HTTPException(status_code=400, detail="max_sources must be between 1 and 100.")
    if (payload.max_sources or 0) > 20 and not entitlements.is_active(str(user["id"])):
        raise HTTPException(status_code=403, detail="Research scans above 20 sources require an active subscription.")
    user_id = supabase_user_id(user)
    started_at = time.monotonic()
    record_backend_analytics(
        "scan_started",
        user_id,
        {
            "requested_count": payload.max_sources or 0,
            "uploaded_source_count": len(payload.uploaded_sources),
            "inclusion_rule_count": len(payload.selected_inclusion_reasons),
            "domain_category": str(payload.domain or "scholarly")[:40],
        },
    )
    try:
        uploaded_sources = parse_uploaded_sources(payload.uploaded_sources, payload.domain or "scholarly")
        dossier_bytes = None
        with tempfile.TemporaryDirectory(prefix="nexus-dossier-") as dossier_directory:
            result_data = pipeline.run_research(
                query=payload.topic,
                max_sources=payload.max_sources,
                additional_sources=uploaded_sources,
                selected_inclusion_reasons=payload.selected_inclusion_reasons,
                output_directory=dossier_directory,
            )
            if hasattr(result_data, "to_dict"):
                result_data = result_data.to_dict()
            elif hasattr(result_data, "model_dump"):
                result_data = result_data.model_dump()
            result_data = jsonable_encoder(result_data)
            dossier_name = str(result_data.get("discovery_report_name") or "")
            dossier_root = Path(dossier_directory).resolve(strict=True)
            dossier_path = (dossier_root / dossier_name).resolve(strict=True)
            if (
                not dossier_name.endswith(".xlsx")
                or dossier_path.parent != dossier_root
                or not dossier_path.is_file()
            ):
                raise RuntimeError("Research dossier was not created in its temporary output directory.")
            dossier_bytes = dossier_path.read_bytes()
            result_data["excel_report_saved_at"] = dossier_name
            result_data["discovery_report_directory"] = None
    except HTTPException:
        record_backend_analytics(
            "scan_failed", user_id,
            {"duration_ms": elapsed_milliseconds(started_at), "error_category": "client_request"},
        )
        raise
    except Exception as error:
        record_backend_analytics(
            "scan_failed", user_id,
            {"duration_ms": elapsed_milliseconds(started_at), "error_category": normalized_error_category(error)},
        )
        raise HTTPException(status_code=500, detail=str(error)) from error
    if not isinstance(result_data, dict):
        record_backend_analytics(
            "scan_failed", user_id,
            {"duration_ms": elapsed_milliseconds(started_at), "error_category": "invalid_result"},
        )
        raise HTTPException(status_code=500, detail="Research pipeline returned an invalid result.")
    try:
        database = require_supabase_database()
        result_data["dossier_download"] = dossier_download_status(user)
        run_id = uuid4()
        storage_path = f"{supabase_user_id(user)}/{run_id}/{result_data['discovery_report_name']}"
        if not dossier_bytes:
            raise RuntimeError("Research dossier was empty.")
        database.upload_storage_object(
            DOSSIER_STORAGE_BUCKET,
            storage_path,
            dossier_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        result_data["excel_dossier_storage_path"] = storage_path
        try:
            run_record = database.insert(
                "research_runs",
                {
                    "id": str(run_id),
                    "user_id": supabase_user_id(user),
                    "query": payload.topic.strip(),
                    "result": result_data,
                },
            )
            included_sources = result_data.get("included")
            excluded_sources = result_data.get("excluded")
            dossier_record = database.insert(
                "saved_dossiers",
                {
                    "user_id": supabase_user_id(user),
                    "title": payload.topic.strip()[:200] or "Research dossier",
                    "payload": {
                        "research_run_id": run_record["id"],
                        "query": payload.topic.strip(),
                        "status": result_data.get("status"),
                        "discovery_report_name": result_data.get("discovery_report_name"),
                        "included_count": len(included_sources) if isinstance(included_sources, list) else 0,
                        "excluded_count": len(excluded_sources) if isinstance(excluded_sources, list) else 0,
                    },
                },
            )
        except Exception:
            try:
                database.request(
                    "DELETE",
                    "research_runs",
                    params={
                        "id": f"eq.{run_id}",
                        "user_id": f"eq.{supabase_user_id(user)}",
                    },
                )
            except Exception:
                logger.exception("Could not clean up research-run row after dossier persistence failed.")
            try:
                database.delete_storage_object(DOSSIER_STORAGE_BUCKET, storage_path)
            except Exception:
                logger.exception("Could not clean up dossier storage after research persistence failed.")
            raise
        response_data = dict(result_data)
        response_data["research_run_id"] = run_record["id"]
        response_data["saved_dossier_id"] = dossier_record["id"]
        response_data.pop("excel_dossier_storage_path", None)
        source_metrics = source_metadata_metrics(
            (result_data.get("included") or []) + (result_data.get("excluded") or [])
        )
        completion_properties = {
            "duration_ms": elapsed_milliseconds(started_at),
            "requested_count": payload.max_sources or 0,
            "included_count": len(result_data.get("included") or []),
            "excluded_count": len(result_data.get("excluded") or []),
            **source_metrics,
        }
        record_backend_analytics("scan_completed", user_id, completion_properties)
        record_backend_analytics(
            "excel_export_completed",
            user_id,
            {
                "duration_ms": completion_properties["duration_ms"],
                "included_count": completion_properties["included_count"],
                "excluded_count": completion_properties["excluded_count"],
                "cache_hit": False,
                "outcome_category": "stored",
            },
        )
        return response_data
    except HTTPException:
        record_backend_analytics(
            "scan_failed", user_id,
            {"duration_ms": elapsed_milliseconds(started_at), "error_category": "client_request"},
        )
        raise
    except Exception as error:
        record_backend_analytics(
            "scan_failed", user_id,
            {"duration_ms": elapsed_milliseconds(started_at), "error_category": normalized_error_category(error)},
        )
        raise HTTPException(status_code=503, detail="Research completed but could not be saved.") from error


@app.get("/v1/research/{run_id}/dossier")
async def download_research_dossier(
    run_id: UUID,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    started_at = time.monotonic()
    user = require_supabase_user(authorization)
    user_id = supabase_user_id(user)
    require_api_access(x_api_key)
    database = require_supabase_database()
    rows = database.request(
        "GET",
        "research_runs",
        params={
            "id": f"eq.{run_id}",
            "user_id": f"eq.{supabase_user_id(user)}",
            "select": "result",
            "limit": 1,
        },
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Research run not found.")

    result_data = rows[0].get("result") or {}
    storage_path = result_data.get("excel_dossier_storage_path")
    filename = str(result_data.get("discovery_report_name") or "")
    expected_storage_path = f"{supabase_user_id(user)}/{run_id}/{filename}"
    if (
        not filename.endswith(".xlsx")
        or Path(filename).name != filename
        or storage_path != expected_storage_path
    ):
        raise HTTPException(status_code=404, detail="This research run has no downloadable Excel dossier.")
    try:
        dossier_bytes = database.download_storage_object(DOSSIER_STORAGE_BUCKET, storage_path)
    except Exception as error:
        record_backend_analytics(
            "excel_download_failed",
            user_id,
            {"duration_ms": elapsed_milliseconds(started_at), "cache_hit": True, "error_category": "dependency_failure"},
        )
        raise HTTPException(status_code=503, detail="The saved Excel dossier is unavailable.") from error
    if not dossier_bytes:
        record_backend_analytics(
            "excel_download_failed",
            user_id,
            {"duration_ms": elapsed_milliseconds(started_at), "cache_hit": True, "error_category": "empty_document"},
        )
        raise HTTPException(status_code=503, detail="The saved Excel dossier is empty.")

    if is_dossier_download_unlimited(user):
        download_status = {"unlimited": True, "remaining": None}
    else:
        try:
            downloads_remaining = database.request(
                "POST",
                "rpc/nexus_claim_dossier_download",
                json={"p_user_id": supabase_user_id(user)},
            )
            downloads_remaining = int(downloads_remaining)
        except Exception as error:
            record_backend_analytics(
                "excel_download_failed",
                user_id,
                {"duration_ms": elapsed_milliseconds(started_at), "cache_hit": True, "error_category": "dependency_failure"},
            )
            raise HTTPException(status_code=503, detail="Could not verify dossier download allowance.") from error
        if downloads_remaining < 0:
            record_backend_analytics(
                "excel_download_failed",
                user_id,
                {"duration_ms": elapsed_milliseconds(started_at), "cache_hit": True, "error_category": "quota_exhausted"},
            )
            raise HTTPException(
                status_code=403,
                detail="You have used all 3 free Excel dossier downloads. Upgrade your plan for more downloads.",
            )
        download_status = {"unlimited": False, "remaining": downloads_remaining}

    response = Response(
        content=dossier_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
            "X-Dossier-Downloads-Remaining": (
                "unlimited" if download_status["unlimited"] else str(download_status["remaining"])
            ),
        },
    )
    record_backend_analytics(
        "excel_download_completed",
        user_id,
        {
            "duration_ms": elapsed_milliseconds(started_at),
            "cache_hit": True,
            "outcome_category": "downloaded",
            "quota_limited": not download_status["unlimited"],
        },
    )
    return response


@app.post("/v1/reports")
async def generate_research_report(
    payload: ReportRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be blank.")
    if payload.report_type not in {"proposal", "full_starter"}:
        raise HTTPException(status_code=400, detail="Unsupported report type.")
    if payload.report_type == "full_starter" and not entitlements.is_active(str(user["id"])):
        raise HTTPException(status_code=403, detail="The Complete Literature Review is available to paid users.")
    user_id = supabase_user_id(user)
    started_at = time.monotonic()
    record_backend_analytics(
        "report_started",
        user_id,
        {
            "report_type": payload.report_type,
            "included_source_count": len(payload.included_sources),
            "uploaded_source_count": len(payload.uploaded_sources),
            "domain_category": str(payload.domain or "scholarly")[:40],
        },
    )
    scribe = None
    try:
        included_sources = list(payload.included_sources)
        uploaded_sources = parse_uploaded_sources(payload.uploaded_sources, payload.domain)
        included_sources.extend(source for source in uploaded_sources if source.get("include"))
        if not included_sources:
            research_result = pipeline.run_research(
                query=topic,
                max_sources=min(max(payload.max_sources, 1), 100),
                additional_sources=uploaded_sources,
            )
            if hasattr(research_result, "to_dict"):
                research_result = research_result.to_dict()
            elif hasattr(research_result, "model_dump"):
                research_result = research_result.model_dump()
            included_sources = research_result.get("included", [])
        included_sources = CitationEngine.referenceable_sources(included_sources)
        if not included_sources:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No included sources have enough publication metadata for a traceable report. "
                    "Each source needs an author, title, year, and publication venue or valid DOI/URL."
                ),
            )
        database = require_supabase_database()
        cache_key = report_cache_key(
            user,
            topic,
            payload.report_type,
            payload.domain,
            included_sources,
        )
        try:
            cached_document = database.download_storage_object(
                DOSSIER_STORAGE_BUCKET, cache_key
            )
        except SupabaseRequestError as error:
            if error.status_code != 404:
                logger.warning(
                    "Could not read cached %s report for user %s: %s",
                    payload.report_type,
                    supabase_user_id(user),
                    error,
                )
            cached_document = None
        except RuntimeError as error:
            logger.warning(
                "Could not read cached %s report for user %s: %s",
                payload.report_type,
                supabase_user_id(user),
                error,
            )
            cached_document = None
        if cached_document:
            response = cached_report_response(
                cached_document,
                cache_key,
                payload.report_type,
            )
            record_backend_analytics(
                "report_completed",
                user_id,
                {
                    "duration_ms": elapsed_milliseconds(started_at),
                    "report_type": payload.report_type,
                    "cache_hit": True,
                    "included_source_count": len(included_sources),
                    "quality_available": False,
                    "provider_attempt_count": 0,
                    "provider_fallback_used": False,
                    "validation_correction_used": False,
                },
            )
            return response
        from app.agents.scribe_agent import ScribeResearchAgent
        from app.reports.dossier_generator import DossierGenerator

        dossier = DossierGenerator().generate_comprehensive_dossier(
            query=topic,
            included_sources=included_sources,
            domain=payload.domain,
            report_type=payload.report_type,
        )
        scribe = ScribeResearchAgent()
        with tempfile.TemporaryDirectory(prefix="nexus-report-") as report_directory:
            if payload.report_type == "full_starter":
                scribe.generate_complete_literature_review(
                    topic=topic,
                    included_sources=included_sources,
                    dossier=dossier,
                    domain=payload.domain,
                    output_directory=report_directory,
                )
            else:
                scribe.generate_apa_dossier_report(
                    topic=topic,
                    included_sources=included_sources,
                    dossier=dossier,
                    domain=payload.domain,
                    output_directory=report_directory,
                )
            report_root = Path(report_directory).resolve(strict=True)
            report_files = list(report_root.glob("*.docx"))
            if len(report_files) != 1:
                raise RuntimeError("Report generation did not produce exactly one document.")
            report_path = report_files[0].resolve(strict=True)
            if report_path.parent != report_root or not report_path.is_file():
                raise RuntimeError("Generated report escaped its temporary output directory.")
            document_bytes = report_path.read_bytes()
            degraded = bool(scribe.fallback_mode)
            if not degraded:
                try:
                    database.upload_storage_object(
                        DOSSIER_STORAGE_BUCKET,
                        cache_key,
                        document_bytes,
                        DOCX_CONTENT_TYPE,
                    )
                except (RuntimeError, SupabaseRequestError) as error:
                    logger.warning(
                        "Could not cache %s report for user %s: %s",
                        payload.report_type,
                        supabase_user_id(user),
                        error,
                    )
            response = {
                "status": "degraded" if degraded else "success",
                "action": (
                    "evidence_grounded_fallback_docx"
                    if degraded else "docx_generation_complete"
                ),
                "generation_mode": (
                    scribe.fallback_mode if degraded else "ai_synthesized"
                ),
                "degraded": degraded,
                "document_name": report_path.name,
                "document_base64": base64.b64encode(document_bytes).decode("ascii"),
                "report_type": payload.report_type,
                "quality_report": jsonable_encoder(dossier.quality_report),
                "cache_hit": False,
                "report_cache_id": None if degraded else report_cache_id(cache_key),
                "report_cache_version": None if degraded else REPORT_CACHE_VERSION,
            }
            telemetry = scribe_telemetry(scribe)
            quality_report = dossier.quality_report
            record_backend_analytics(
                "report_degraded_completed" if degraded else "report_completed",
                user_id,
                {
                    "duration_ms": elapsed_milliseconds(started_at),
                    "report_type": payload.report_type,
                    "cache_hit": False,
                    "included_source_count": len(included_sources),
                    "quality_available": bool(quality_report),
                    "quality_passed": (
                        bool(quality_report.get("passed", True))
                        if isinstance(quality_report, dict) else None
                    ),
                    "outcome_category": "evidence_grounded_fallback" if degraded else "ai_synthesized",
                    **telemetry,
                },
            )
            return response
    except HTTPException:
        record_backend_analytics(
            "report_failed",
            user_id,
            {
                "duration_ms": elapsed_milliseconds(started_at),
                "report_type": payload.report_type,
                "error_category": "client_request",
                **(scribe_telemetry(scribe) if scribe else {}),
            },
        )
        raise
    except ReportSynthesisError as error:
        logger.warning("Word report failed its synthesis quality gate: %s", error)
        record_backend_analytics(
            "report_failed",
            user_id,
            {
                "duration_ms": elapsed_milliseconds(started_at),
                "report_type": payload.report_type,
                "error_category": "quality_or_provider",
                **(scribe_telemetry(scribe) if scribe else {}),
            },
        )
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("Word report generation failed for report type %s.", payload.report_type)
        record_backend_analytics(
            "report_failed",
            user_id,
            {
                "duration_ms": elapsed_milliseconds(started_at),
                "report_type": payload.report_type,
                "error_category": normalized_error_category(error),
                **(scribe_telemetry(scribe) if scribe else {}),
            },
        )
        raise HTTPException(status_code=500, detail="Report generation failed.") from error


@app.get("/v1/reports/cache/{cache_id}")
async def download_cached_research_report(
    cache_id: str,
    report_type: str = "proposal",
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    started_at = time.monotonic()
    user = require_supabase_user(authorization)
    user_id = supabase_user_id(user)
    require_api_access(x_api_key)
    if report_type not in {"proposal", "full_starter"}:
        raise HTTPException(status_code=400, detail="Unsupported report type.")
    cache_digest = parse_report_cache_id(cache_id)
    if not cache_digest:
        raise HTTPException(
            status_code=410,
            detail="This cached report is outdated. Generate a new report to download the corrected version.",
        )
    cache_key = (
        f"{supabase_user_id(user)}/{REPORT_CACHE_PREFIX}/{cache_digest}/"
        f"{report_type}-report.docx"
    )
    try:
        document_bytes = require_supabase_database().download_storage_object(
            DOSSIER_STORAGE_BUCKET, cache_key
        )
    except SupabaseRequestError as error:
        if error.status_code == 404:
            record_backend_analytics(
                "report_cache_redownload_failed", user_id,
                {"duration_ms": elapsed_milliseconds(started_at), "report_type": report_type, "error_category": "not_found"},
            )
            raise HTTPException(status_code=404, detail="Cached report not found.") from error
        logger.warning(
            "Could not download cached %s report for user %s: %s",
            report_type,
            supabase_user_id(user),
            error,
        )
        record_backend_analytics(
            "report_cache_redownload_failed", user_id,
            {"duration_ms": elapsed_milliseconds(started_at), "report_type": report_type, "error_category": "dependency_failure"},
        )
        raise HTTPException(status_code=503, detail="Cached report download is unavailable.") from error
    except RuntimeError as error:
        logger.warning(
            "Could not download cached %s report for user %s: %s",
            report_type,
            supabase_user_id(user),
            error,
        )
        record_backend_analytics(
            "report_cache_redownload_failed", user_id,
            {"duration_ms": elapsed_milliseconds(started_at), "report_type": report_type, "error_category": "dependency_failure"},
        )
        raise HTTPException(status_code=503, detail="Cached report download is unavailable.") from error
    response = cached_report_response(document_bytes, cache_key, report_type)
    record_backend_analytics(
        "report_cache_redownload_completed",
        user_id,
        {
            "duration_ms": elapsed_milliseconds(started_at),
            "report_type": report_type,
            "cache_hit": True,
            "outcome_category": "downloaded",
        },
    )
    return response


@app.get("/v1/research")
async def list_research_runs(
    limit: int = 50,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    database = require_supabase_database()
    return database.request(
        "GET",
        "research_runs",
        params={
            "user_id": f"eq.{supabase_user_id(user)}",
            "select": "id,query,created_at",
            "order": "created_at.desc",
            "limit": min(max(limit, 1), 100),
        },
    )


@app.get("/v1/research/{run_id}")
async def get_research_run(
    run_id: UUID,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    rows = require_supabase_database().request(
        "GET",
        "research_runs",
        params={
            "id": f"eq.{run_id}",
            "user_id": f"eq.{supabase_user_id(user)}",
            "select": "*",
            "limit": 1,
        },
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Research run not found.")
    record = dict(rows[0])
    result_data = record.get("result")
    if isinstance(result_data, dict):
        record["result"] = dict(result_data)
        record["result"].pop("excel_dossier_storage_path", None)
    return record


@app.get("/v1/dossiers")
async def list_saved_dossiers(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    return require_supabase_database().request(
        "GET",
        "saved_dossiers",
        params={
            "user_id": f"eq.{supabase_user_id(user)}",
            "select": "*",
            "order": "updated_at.desc",
            "limit": 100,
        },
    )


@app.post("/v1/dossiers")
async def save_dossier(
    payload: SavedDossierRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    return require_supabase_database().insert(
        "saved_dossiers",
        {
            "user_id": supabase_user_id(user),
            "title": payload.title.strip(),
            "payload": payload.payload,
        },
    )


@app.delete("/v1/dossiers/{dossier_id}")
async def delete_saved_dossier(
    dossier_id: UUID,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    deleted = require_supabase_database().request(
        "DELETE",
        "saved_dossiers",
        params={
            "id": f"eq.{dossier_id}",
            "user_id": f"eq.{supabase_user_id(user)}",
            "select": "id",
        },
        prefer="return=representation",
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved dossier not found.")
    return {"status": "deleted"}


@app.get("/v1/sources")
async def list_saved_sources(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    return require_supabase_database().request(
        "GET",
        "saved_sources",
        params={
            "user_id": f"eq.{supabase_user_id(user)}",
            "select": "*",
            "order": "created_at.desc",
            "limit": 200,
        },
    )


@app.post("/v1/sources")
async def save_source(
    payload: SavedSourceRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    source = payload.source
    source_key = next(
        (
            str(source[key]).strip().lower()
            for key in ("doi", "id", "url", "title")
            if source.get(key)
        ),
        None,
    )
    if not source_key:
        raise HTTPException(status_code=400, detail="Saved sources must include a DOI, ID, URL, or title.")
    database = require_supabase_database()
    records = database.request(
        "POST",
        "saved_sources",
        params={"on_conflict": "user_id,source_key"},
        json={
            "user_id": supabase_user_id(user),
            "source_key": source_key[:500],
            "source": source,
        },
        prefer="resolution=merge-duplicates,return=representation",
    )
    if not isinstance(records, list) or not records:
        raise HTTPException(status_code=503, detail="Supabase did not return the saved source.")
    return records[0]


@app.delete("/v1/sources/{source_id}")
async def delete_saved_source(
    source_id: UUID,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    deleted = require_supabase_database().request(
        "DELETE",
        "saved_sources",
        params={
            "id": f"eq.{source_id}",
            "user_id": f"eq.{supabase_user_id(user)}",
            "select": "id",
        },
        prefer="return=representation",
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved source not found.")
    return {"status": "deleted"}

@app.post("/v1/analytics")
async def log_telemetry_event(
    event: AnalyticsEvent,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    try:
        analytics.record(
            event_name=event.event,
            user_id=supabase_user_id(user),
            session_id=event.session_id or "unknown",
            properties=privacy_safe_analytics_context(event.context),
            occurred_at=event.timestamp,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        logger.exception("Could not persist client analytics event %s.", event.event)
        return {"status": "accepted"}
    return {"status": "logged"}


@app.get("/v1/admin/analytics")
async def get_admin_analytics(days: int = 30, x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    return analytics.summary(days=days)


@app.post("/v1/paypal/orders")
async def create_paypal_order(
    payload: PayPalOrderRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    user_id = supabase_user_id(user)
    try:
        order = paypal.create_order(payload.plan, user_id)
        record_backend_analytics(
            "checkout_started", user_id,
            {"provider": "paypal", "plan": payload.plan, "order_id": order.get("id")},
        )
        return order
    except (RuntimeError, ValueError) as error:
        record_backend_analytics(
            "payment_failed", user_id,
            {"provider": "paypal", "error_code": "CONFIGURATION"},
        )
        raise HTTPException(status_code=503, detail=str(error))
    except Exception as error:
        record_backend_analytics(
            "payment_failed", user_id,
            {"provider": "paypal", "error_code": "PAYPAL_API_ERROR"},
        )
        raise HTTPException(status_code=502, detail="PayPal order creation failed.")


@app.post("/v1/paypal/subscriptions")
async def create_paypal_subscription(
    payload: PayPalOrderRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    user_id = supabase_user_id(user)
    try:
        subscription = paypal.create_subscription(payload.plan, user_id)
        record_backend_analytics(
            "checkout_started", user_id,
            {
                "provider": "paypal",
                "payment_type": "subscription",
                "plan": payload.plan,
                "subscription_id": subscription.get("id"),
            },
        )
        if subscription.get("id"):
            entitlements.upsert(
                user_id,
                "paypal",
                subscription["id"],
                "PENDING",
                plan=payload.plan,
            )
        return subscription
    except (RuntimeError, ValueError) as error:
        record_backend_analytics(
            "payment_failed", user_id,
            {"provider": "paypal", "error_code": "CONFIGURATION"},
        )
        raise HTTPException(status_code=503, detail=str(error))
    except Exception:
        record_backend_analytics(
            "payment_failed", user_id,
            {"provider": "paypal", "error_code": "PAYPAL_API_ERROR"},
        )
        raise HTTPException(status_code=502, detail="PayPal subscription creation failed.")


@app.post("/v1/paypal/capture")
async def capture_paypal_order(
    payload: PayPalCaptureRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    user_id = supabase_user_id(user)
    try:
        result = paypal.capture_order(payload.order_id)
        status = result.get("status")
        event_name = "payment_completed" if status == "COMPLETED" else "payment_pending"
        if status == "COMPLETED":
            purchase_units = result.get("purchase_units") or []
            custom_id = (purchase_units[0] if purchase_units else {}).get("custom_id")
            if custom_id:
                entitlements.upsert(
                    custom_id,
                    "paypal",
                    payload.order_id,
                    "COMPLETED",
                    plan=(purchase_units[0].get("reference_id") if purchase_units else None),
                )
        record_backend_analytics(
            event_name, user_id,
            {"provider": "paypal", "order_id": payload.order_id, "status": status},
        )
        return result
    except Exception:
        record_backend_analytics(
            "payment_failed", user_id,
            {
                "provider": "paypal",
                "error_code": "CAPTURE_FAILED",
                "order_id": payload.order_id,
            },
        )
        raise HTTPException(status_code=502, detail="PayPal payment capture failed.")


@app.get("/v1/entitlements/{user_id}")
async def get_entitlement(
    user_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    if not user_id or len(user_id) > 200:
        raise HTTPException(status_code=400, detail="Invalid user ID.")
    allowed_ids = {str(user["id"])}
    if user.get("email"):
        allowed_ids.add(str(user["email"]))
    if user_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Cannot access another user's entitlements.")
    record = entitlements.get(str(user["id"]))
    return {
        "user_id": user_id,
        "active": bool(record and record["status"] in {"ACTIVE", "APPROVED", "COMPLETED"}),
        "entitlement": record,
    }


@app.post("/v1/paypal/webhook")
async def paypal_webhook(request: Request):
    event = await request.json()
    headers = {key.upper(): value for key, value in request.headers.items()}
    try:
        if not paypal.verify_webhook_signature(headers, event):
            raise HTTPException(status_code=400, detail="Invalid PayPal webhook signature.")
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error))

    event_id = event.get("id")
    if not entitlements.claim_event(event_id):
        return {"status": "already_processed"}

    resource = event.get("resource", {})
    event_type = event.get("event_type", "")
    provider_id = resource.get("id") or resource.get("billing_agreement_id")
    user_id = resource.get("custom_id")
    if not user_id and provider_id:
        prior = entitlements.get_by_provider("paypal", provider_id)
        user_id = (prior.get("user_id") or prior.get("user_key")) if prior else None
    if "ACTIVATED" in event_type or "PAYMENT.COMPLETED" in event_type:
        status = "ACTIVE"
    elif any(value in event_type for value in ("CANCEL", "SUSPEND", "EXPIRED", "REVOKED")):
        status = "CANCELLED"
    else:
        status = "PENDING"
    if provider_id and user_id:
        entitlements.upsert(
            user_id,
            "paypal",
            provider_id,
            status,
            plan=resource.get("plan_id"),
        )
    record_backend_analytics(
        "paypal_webhook_received",
        user_id or "anonymous",
        {"event_type": event_type, "provider_id": provider_id, "status": status},
    )
    return {"status": "processed"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("cloud_app.py", host="0.0.0.0", port=8000, reload=True)
