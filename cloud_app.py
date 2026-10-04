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
from fastapi.responses import FileResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, constr, field_validator
from typing import Optional, List, Dict, Any, Literal
from app.supabase_store import SupabaseRequestError, SupabaseRestClient
from app.research.research_pipeline import ResearchPipeline
from app.analytics.event_store import AnalyticsEventStore
from app.analytics import catalog, metrics_engine, tracing  # noqa: F401 (catalog registers the metrics)
from app.analytics.event_store import MAX_FETCHED_EVENTS
from app.analytics.health import instrumentation_health
from app.analytics.schema import event_source as schema_event_source
from app.analytics.tracing import traced
from app.analytics.context import (
    accept_request_id, configure_logging, current_request_id, reset_request_id, set_request_id,
)
from app.analytics.schema import CLIENT, EXTENSION, SERVER, WEB, build_properties
from app.payments.paypal import PayPalClient, PayPalError
from app.payments.catalog import all_packs, get_pack
from app.payments.checkout import CheckoutError, capture_pack_order, create_pack_checkout, handle_paypal_event
from app.payments import exposure
from app.reports.snapshot import snapshot_from_docx
from app.payments.entitlements import EntitlementStore
from app.synthesis.citation_engine import CitationEngine
from app.research.spelling import normalize_topic_spelling
from app.agents.scribe_agent import ReportSynthesisError, ReportProviderLimitError
from app.reports.queue_config import default_queue_config, ReportQueueConfig
from app.reports.report_queue import global_queue_manager, QueuedReportJob
from app.notifications.notification_service import NotificationService
from app.synthesis.providers import SynthesisProviderError, DegradationLogger, SynthesisProviderRegistry
from app.synthesis.errors import classify_provider_error
from app.payments.config import default_pricing_config, PricingConfig
from app.analytics.ab_experiment import ExperimentService
from app.reports.proposal_service import AI_SYNTHESIZED, generate_proposal_docx, ProposalValidationError
from app.synthesis.call_ledger import RequestLedger
from fastapi.concurrency import run_in_threadpool
from app.reports.queue_worker import start_queue_worker, stop_queue_worker
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start/stop background tasks."""
    # Startup
    await start_queue_worker()
    yield
    # Shutdown
    await stop_queue_worker()


configure_logging()
app = FastAPI(title="Nexus Research AI Gateway", version="1.0.0", lifespan=lifespan)
logger = logging.getLogger(__name__)


@app.middleware("http")
async def assign_request_id(request: Request, call_next):
    """Give every request one id that appears in logs, analytics events and the response."""
    request_id = accept_request_id(request.headers.get("x-request-id"))
    token = set_request_id(request_id)
    try:
        response = await call_next(request)
    finally:
        reset_request_id(token)
    response.headers["X-Request-ID"] = request_id
    return response


allowed_origins = os.getenv("NEXUS_ALLOWED_ORIGINS", os.getenv("CORS_origins", "*"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-Dossier-Downloads-Remaining", "X-Request-ID"],
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
    source: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


FEEDBACK_REASONS = ("inaccurate", "not_synthesized", "citations", "formatting", "too_long", "too_short")


class FeedbackRequest(BaseModel):
    """A rating of one delivered report. Fixed reasons only; free text is never collected."""
    reference: constr(pattern=r"^[A-Za-z0-9._-]{8,64}$")
    rating: Literal["up", "down"]
    reasons: List[str] = Field(default_factory=list, max_length=len(FEEDBACK_REASONS))
    report_type: Literal["proposal", "full_starter"] = "proposal"

    @field_validator("reasons")
    @classmethod
    def reasons_must_be_known(cls, reasons):
        unknown = [reason for reason in reasons if reason not in FEEDBACK_REASONS]
        if unknown:
            raise ValueError(f"Unknown feedback reasons: {unknown}")
        return reasons


class CheckoutOrderRequest(BaseModel):
    pack_id: Optional[constr(pattern=r"^[A-Za-z0-9_-]{1,80}$")] = None


class PayPalCaptureRequest(BaseModel):
    order_id: str
    user_id: str = "anonymous"
    bundle_id: Optional[str] = None
    variant: Optional[str] = None

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
    research_run_id: Optional[UUID] = None
    preview: bool = False


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
            properties=build_properties(event_name, properties, SERVER),
        )
    except Exception:
        logger.exception("Could not persist backend analytics event %s.", event_name)


tracing.set_sink(record_backend_analytics)


def elapsed_milliseconds(started_at: float) -> int:
    return max(0, int((time.monotonic() - started_at) * 1000))


def record_llm_calls(user_id: str, ledger) -> None:
    """One event per model call; tokens are billed even when the call's output was unusable."""
    for call in ledger.calls:
        record_backend_analytics("llm_call", user_id, {
            "purpose": call.purpose, "provider": call.provider, "model": call.model,
            "attempt": call.attempt, "outcome": call.outcome, "latency_ms": call.latency_ms,
            "input_tokens": call.input_tokens, "output_tokens": call.output_tokens,
            "http_status": call.http_status, "error_kind": call.error_kind,
        })


def record_proposal_quality(user_id: str, doc, report_type: str) -> None:
    """Stage spans and the quality summary for a proposal that was produced."""
    for stage, duration_ms in doc.timings_ms.items():
        tracing.record_span(user_id, f"report.{stage.removesuffix('_ms')}", duration_ms, report_type=report_type)
    record_backend_analytics("proposal_quality", user_id, dict(doc.quality))


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
        "model_selected", "outcome_category", "tier", "variant", "copy_variant",
        "context", "reason", "headline", "bundle_id", "source_cap", "query_string",
        "estimated_wait", "error_reason", "job_id", "surface", "kind", "placement",
    }
    sensitive_keys = {
        "prompt", "sources", "abstract", "text", "content", "detail", "description",
    }
    safe_context = {}
    for key, value in context.items():
        normalized_key = str(key).strip().lower()
        if (
            normalized_key in sensitive_keys
            or any(part in normalized_key for part in ("prompt", "abstract", "content"))
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
    cache_id = report_cache_id(cache_key)
    return {
        "status": "success",
        "action": "cached_docx_download",
        "generation_mode": "ai_synthesized",
        "degraded": False,
        "document_name": Path(cache_key).name,
        "document_base64": base64.b64encode(document_bytes).decode("ascii"),
        "download_url": f"/v1/reports/cache/{cache_id}/download?report_type={report_type}",
        "report_id": cache_id,
        "report_type": report_type,
        "cache_hit": True,
        "report_cache_id": cache_id,
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
@app.get("/v1/pricing")
async def get_pricing_configuration():
    """Returns current pricing model configuration and bundle options."""
    return default_pricing_config.to_dict()


@app.post("/v1/scan")
async def execute_cloud_scan(
    payload: ScanRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    topic = normalize_topic_spelling(payload.topic.strip())
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be blank.")
    topic_corrected = topic != payload.topic.strip()

    user_id = supabase_user_id(user)
    session_id = x_session_id or "unknown"
    started_at = time.monotonic()
    
    # Check permissions and quota under the configurable pricing model
    user_email = user.get("email")
    permission = entitlements.check_query_permission(user_id, user_email=user_email)
    is_free_user = (permission.get("tier") == "free")
    ab_variant = ExperimentService.get_variant_for_user(user_id)
    run_id_str = str(uuid4())

    if not permission["allowed"]:
        # Blocked by paywall (e.g. 2nd query attempted)
        record_backend_analytics(
            "second_query_attempted",
            user_id,
            {
                "run_id": run_id_str,
                "tier": permission.get("tier", "free"),
                "is_blocked": True,
                "variant": ab_variant,
            },
        )
        record_backend_analytics(
            "paywall_shown",
            user_id,
            {
                "run_id": run_id_str,
                "context": "second_query_attempt",
                "copy_variant": permission.get("paywall_copy", {}).get("variant", default_pricing_config.paywall_copy_variant),
                "variant": ab_variant,
            },
        )
        raise HTTPException(
            status_code=403,
            detail={
                "message": (
                    permission.get("paywall_copy", {}).get("description")
                    or "Free query allowance reached. A Research Pack is required to run more scans."
                ),
                "paywall": permission.get("paywall_copy", {}),
                "requires_bundle": True,
            },
        )

    # Allowed query
    # Source cap calculation: free queries return up to 20 candidates (per spec), paid return requested count (up to 100)
    effective_max_sources = min(payload.max_sources or 20, default_pricing_config.free_candidate_cap) if is_free_user else (payload.max_sources or 20)
    if not 1 <= effective_max_sources <= 100:
        raise HTTPException(status_code=400, detail="max_sources must be between 1 and 100.")

    # Track second_query_attempted if this is user's >= 2nd query (even if allowed by bundle)
    if permission.get("queries_used", 0) >= 1:
        record_backend_analytics(
            "second_query_attempted",
            user_id,
            {
                "run_id": run_id_str,
                "tier": permission.get("tier", "paid"),
                "is_blocked": False,
                "variant": ab_variant,
            },
        )

    # Track query_submitted
    record_backend_analytics(
        "query_submitted",
        user_id,
        {
            "run_id": run_id_str,
            "tier": permission.get("tier", "free"),
            "source_cap": effective_max_sources,
            "variant": ab_variant,
        },
    )

    record_backend_analytics(
        "scan_started",
        user_id,
        {
            "run_id": run_id_str,
            "requested_count": effective_max_sources,
            "uploaded_source_count": len(payload.uploaded_sources),
            "inclusion_rule_count": len(payload.selected_inclusion_reasons),
            "domain_category": str(payload.domain or "scholarly")[:40],
            "variant": ab_variant,
            "topic_corrected": topic_corrected,
        },
    )
    try:
        uploaded_sources = parse_uploaded_sources(payload.uploaded_sources, payload.domain or "scholarly")
        dossier_bytes = None
        with tempfile.TemporaryDirectory(prefix="nexus-dossier-") as dossier_directory:
            with traced(user_id, "scan.discovery"):
                result_data = pipeline.run_research(
                    query=topic,
                    max_sources=effective_max_sources,
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
            {"run_id": run_id_str, "duration_ms": elapsed_milliseconds(started_at), "error_category": "client_request", "variant": ab_variant},
        )
        raise
    except Exception as error:
        record_backend_analytics(
            "scan_failed", user_id,
            {"run_id": run_id_str, "duration_ms": elapsed_milliseconds(started_at), "error_category": normalized_error_category(error), "variant": ab_variant},
        )
        raise HTTPException(status_code=500, detail=str(error)) from error
    if not isinstance(result_data, dict):
        record_backend_analytics(
            "scan_failed", user_id,
            {"run_id": run_id_str, "duration_ms": elapsed_milliseconds(started_at), "error_category": "invalid_result", "variant": ab_variant},
        )
        raise HTTPException(status_code=500, detail="Research pipeline returned an invalid result.")

    # Guarantee full non-truncated exclusion audit for free and paid queries alike
    if "excluded" not in result_data or result_data["excluded"] is None:
        result_data["excluded"] = []
    
    # Increment query usage for user
    entitlements.increment_query_usage(user_id)
    
    # Attach A/B variant and quota info
    result_data["ab_variant"] = ab_variant
    result_data["is_paid_user"] = not is_free_user

    # Add quota information for paywall moments
    quota_check = entitlements.check_query_permission(str(user["id"]))
    result_data["queries_remaining"] = quota_check.get("queries_remaining")
    result_data["free_allowance"] = quota_check.get("free_allowance")
    result_data["requires_paywall"] = quota_check.get("requires_paywall", False)
    result_data["paywall_copy"] = quota_check.get("paywall_copy")

    try:
        database = require_supabase_database()
        result_data["dossier_download"] = dossier_download_status(user)
        run_id = UUID(run_id_str)
        storage_path = f"{supabase_user_id(user)}/{run_id}/{result_data['discovery_report_name']}"
        if not dossier_bytes:
            raise RuntimeError("Research dossier was empty.")
        with traced(user_id, "scan.export"):
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
                    "query": topic,
                    "result": result_data,
                },
            )
            included_sources = result_data.get("included")
            excluded_sources = result_data.get("excluded")
            dossier_record = database.insert(
                "saved_dossiers",
                {
                    "user_id": supabase_user_id(user),
                    "title": topic[:200] or "Research dossier",
                    "payload": {
                        "research_run_id": run_record["id"],
                        "query": topic,
                        "status": result_data.get("status"),
                        "discovery_report_name": result_data.get("discovery_report_name"),
                        "included_count": len(included_sources) if isinstance(included_sources, list) else 0,
                        "excluded_count": len(excluded_sources) if isinstance(excluded_sources, list) else 0,
                        "ab_variant": ab_variant,
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
        entitled = exposure.is_entitled(entitlements, user_id, user_email)
        if not entitled:
            record_backend_analytics(
                "snapshot_served", user_id,
                {"surface": "results", "run_id": run_id_str, "hidden_count": max(0, len(result_data.get("included") or []) - exposure.PREVIEW_ROWS) + max(0, len(result_data.get("excluded") or []) - exposure.PREVIEW_ROWS)},
            )
        response_data = exposure.results_for(response_data, entitled)
        source_metrics = source_metadata_metrics(
            (result_data.get("included") or []) + (result_data.get("excluded") or [])
        )
        completion_properties = {
            "run_id": run_id_str,
            "duration_ms": elapsed_milliseconds(started_at),
            "requested_count": effective_max_sources,
            "included_count": len(result_data.get("included") or []),
            "excluded_count": len(result_data.get("excluded") or []),
            "variant": ab_variant,
            **source_metrics,
        }
        record_backend_analytics("scan_completed", user_id, completion_properties)
        record_backend_analytics(
            "excel_export_completed",
            user_id,
            {
                "run_id": run_id_str,
                "duration_ms": completion_properties["duration_ms"],
                "included_count": completion_properties["included_count"],
                "excluded_count": completion_properties["excluded_count"],
                "cache_hit": False,
                "outcome_category": "stored",
                "variant": ab_variant,
            },
        )
        return response_data
    except HTTPException:
        record_backend_analytics(
            "scan_failed", user_id,
            {"run_id": run_id_str, "duration_ms": elapsed_milliseconds(started_at), "error_category": "client_request", "variant": ab_variant},
        )
        raise
    except Exception as error:
        record_backend_analytics(
            "scan_failed", user_id,
            {"run_id": run_id_str, "duration_ms": elapsed_milliseconds(started_at), "error_category": normalized_error_category(error), "variant": ab_variant},
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

    if not exposure.is_entitled(entitlements, user_id, user.get("email")) and exposure.free_dossier_downloads() == 0:
        record_backend_analytics("download_blocked", user_id, {"surface": "excel", "run_id": str(run_id)})
        raise upgrade_required("excel", "The full Excel dossier is included with a Research Pack.")

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
                detail={
                    "message": "You have used all 3 free Excel dossier downloads. Upgrade your plan for more downloads.",
                    "error_code": "download_quota_exhausted",
                    "downloads_remaining": downloads_remaining,
                    "downloads_limit": 3,
                    "is_paid": entitlements.is_active(user_id),
                },
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
    topic = normalize_topic_spelling(payload.topic.strip())
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be blank.")
    if payload.report_type not in {"proposal", "full_starter"}:
        raise HTTPException(status_code=400, detail="Unsupported report type.")
    user_id = supabase_user_id(user)
    entitled = exposure.is_entitled(entitlements, user_id, user.get("email"))
    if payload.report_type == "full_starter" and not entitled:
        raise HTTPException(status_code=403, detail="The Complete Literature Review is available to paid users.")
    # Free users never receive a document. They may ask for a snapshot of a proposal built from one of
    # their own scans; anything else is refused before a model is called.
    snapshot_only = not entitled
    if snapshot_only and not (payload.preview and payload.research_run_id):
        record_backend_analytics("download_blocked", user_id, {"surface": "word"})
        raise upgrade_required("word", "The full Word proposal is included with a Research Pack.")
    started_at = time.monotonic()
    record_backend_analytics(
        "report_started",
        user_id,
        {
            "report_type": payload.report_type,
            "included_source_count": len(payload.included_sources),
            "uploaded_source_count": len(payload.uploaded_sources),
            "domain_category": str(payload.domain or "scholarly")[:40],
            "topic_hash": hashlib.sha256(topic.casefold().encode("utf-8")).hexdigest()[:12],
        },
    )
    scribe = None
    credit_claimed = False
    try:
        if payload.research_run_id:
            # The saved run is the source of truth: the browser's list may be a truncated preview.
            included_sources = load_run_included_sources(user_id, payload.research_run_id)
            uploaded_sources = []
        else:
            included_sources = list(payload.included_sources)
            uploaded_sources = parse_uploaded_sources(payload.uploaded_sources, payload.domain)
            included_sources.extend(source for source in uploaded_sources if source.get("include"))
        if not included_sources and snapshot_only:
            raise HTTPException(status_code=422, detail="This scan has no included sources to build a proposal from.")
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
            if error.status_code != 404 and "not found" not in str(error).lower():
                logger.warning(
                    "Could not read cached %s report for user %s: %s",
                    payload.report_type,
                    supabase_user_id(user),
                    error,
                )
            else:
                logger.debug(
                    "Cache miss for %s report for user %s",
                    payload.report_type,
                    supabase_user_id(user),
                )
            cached_document = None
        except RuntimeError as error:
            if "not found" in str(error).lower() or "404" in str(error):
                logger.debug(
                    "Cache miss for %s report for user %s",
                    payload.report_type,
                    supabase_user_id(user),
                )
            else:
                logger.warning(
                    "Could not read cached %s report for user %s: %s",
                    payload.report_type,
                    supabase_user_id(user),
                    error,
                )
            cached_document = None
        if cached_document:
            if snapshot_only:
                # Already generated (e.g. an earlier preview): costs nothing, so it uses no credit.
                return snapshot_response(
                    user_id, cached_document, payload.report_type, current_request_id() or str(uuid4()),
                    cache_hit=True, generation_mode=AI_SYNTHESIZED,
                )
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

        # Proposal generation: deterministic templates with extracted metadata
        if payload.report_type == "proposal":
            reference_id = current_request_id() or str(uuid4())
            if snapshot_only:
                try:
                    credit_claimed = await run_in_threadpool(
                        entitlements.claim_feature_use, user_id, WORD_PREVIEW_FEATURE, exposure.free_word_previews()
                    )
                except (RuntimeError, SupabaseRequestError) as error:
                    logger.warning("Could not verify the free preview allowance: %s", error)
                    raise HTTPException(status_code=503, detail="Could not verify your free preview. Please try again.") from error
                if not credit_claimed:
                    record_backend_analytics("download_blocked", user_id, {"surface": "word"})
                    raise upgrade_required(
                        "word", "You have used your free proposal preview this month. A Research Pack unlocks the full proposal."
                    )
            try:
                logger.info("Proposal: generating from %d sources (reference=%s)",
                           len(included_sources), reference_id)

                # Blocking model call and DOCX rendering: keep them off the event loop
                ledger = RequestLedger(request_id=reference_id)
                try:
                    doc = await run_in_threadpool(
                        generate_proposal_docx,
                        topic,
                        payload.domain,
                        included_sources,
                        None,
                        ledger,
                    )
                finally:
                    record_llm_calls(user_id, ledger)
                record_proposal_quality(user_id, doc, payload.report_type)

                document_bytes = doc.document_bytes
                word_count = doc.word_count
                synthesized = doc.generation_mode == AI_SYNTHESIZED

                logger.info("Proposal: generated (mode=%s, %d words, %d bytes)",
                           doc.generation_mode, word_count, len(document_bytes))

                response = {
                    "status": "ready",
                    "action": "docx_generation_complete",
                    "generation_mode": doc.generation_mode,
                    "degraded": not synthesized,
                    "document_name": doc.document_name,
                    "document_base64": base64.b64encode(document_bytes).decode("ascii"),
                    "report_type": payload.report_type,
                    "cache_hit": False,
                    "reference": reference_id,
                }
                if doc.synthesis_note:
                    response["synthesis_note"] = doc.synthesis_note
                    response["synthesis_failure"] = doc.synthesis_failure

                # Only AI-synthesized documents are cached. A fallback is returned inline so the
                # next request retries synthesis instead of replaying the weaker document.
                if synthesized:
                    with traced(user_id, "report.storage_upload", report_type=payload.report_type):
                        database.upload_storage_object(
                            DOSSIER_STORAGE_BUCKET,
                            cache_key,
                            document_bytes,
                            DOCX_CONTENT_TYPE,
                        )
                    cache_id_val = report_cache_id(cache_key)
                    response.update({
                        "download_url": f"/v1/reports/cache/{cache_id_val}/download?report_type={payload.report_type}",
                        "report_id": cache_id_val,
                        "report_cache_id": cache_id_val,
                        "report_cache_version": REPORT_CACHE_VERSION,
                    })

                record_backend_analytics(
                    "report_completed",
                    user_id,
                    {
                        "duration_ms": elapsed_milliseconds(started_at),
                        "report_type": payload.report_type,
                        "cache_hit": False,
                        "included_source_count": len(included_sources),
                        "word_count": word_count,
                        "outcome_category": doc.generation_mode,
                        "tier": "free" if snapshot_only else "paid",
                    },
                )
                logger.info("Proposal: completed successfully (reference=%s)", reference_id)
                if snapshot_only:
                    return snapshot_response(
                        user_id, document_bytes, payload.report_type, reference_id,
                        cache_hit=False, generation_mode=doc.generation_mode,
                    )
                return response

            except ProposalValidationError as error:
                # User-fixable: validation failure (missing themes, too brief, etc.)
                logger.warning("Proposal: validation failed (reference=%s): %s", reference_id, error.errors)
                release_preview_credit(user_id, credit_claimed)
                raise HTTPException(status_code=422, detail={
                    "message": str(error),
                    "error_code": "proposal_validation_failed",
                    "retryable": False,
                    "reference": reference_id,
                    "is_paid": entitlements.is_active(user_id),
                })

            except HTTPException:
                release_preview_credit(user_id, credit_claimed)
                raise

            except Exception as error:
                # System error: rendering, I/O, etc.
                logger.exception("Proposal: generation failed (reference=%s)", reference_id)
                release_preview_credit(user_id, credit_claimed)
                raise HTTPException(status_code=500, detail={
                    "message": f"Proposal generation failed: {str(error)}",
                    "error_code": "proposal_generation_failed",
                    "retryable": False,
                    "reference": reference_id,
                    "is_paid": entitlements.is_active(user_id),
                })

        # Legacy path for full_starter
        from app.agents.scribe_agent import ScribeResearchAgent
        from app.reports.dossier_generator import DossierGenerator

        try:
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
                cache_id_val = report_cache_id(cache_key)
                response = {
                    "status": "ready",
                    "action": "docx_generation_complete",
                    "generation_mode": "ai_synthesized",
                    "degraded": False,
                    "document_name": report_path.name,
                    "document_base64": base64.b64encode(document_bytes).decode("ascii"),
                    "download_url": f"/v1/reports/cache/{cache_id_val}/download?report_type={payload.report_type}",
                    "report_id": cache_id_val,
                    "report_type": payload.report_type,
                    "quality_report": jsonable_encoder(dossier.quality_report),
                    "cache_hit": False,
                    "report_cache_id": cache_id_val,
                    "report_cache_version": REPORT_CACHE_VERSION,
                }
                telemetry = scribe_telemetry(scribe)
                quality_report = dossier.quality_report
                record_backend_analytics(
                    "report_completed",
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
                        "outcome_category": "ai_synthesized",
                        **telemetry,
                    },
                )
                return response
        except (ReportProviderLimitError, SynthesisProviderError) as provider_err:
            logger.warning("Synthesis provider failed on submit, enqueueing report request: %s", provider_err)
            is_paid_user = entitlements.is_active(user_id)
            ab_variant = ExperimentService.get_variant_for_user(user_id)

            # Classify the error for structured queueing response
            provider = getattr(provider_err, "provider", "synthesis_provider") or "synthesis_provider"
            classification = classify_provider_error(provider_err, provider)

            job = global_queue_manager.enqueue(
                user_id=user_id,
                topic=topic,
                report_type=payload.report_type,
                domain=payload.domain,
                included_sources=included_sources,
                initial_error=str(provider_err),
                user_email=user.get("email"),
                is_paid=is_paid_user,
                retry_after_seconds=classification.retry_after_seconds,
            )
            record_backend_analytics(
                "report_queued",
                user_id,
                {
                    "duration_ms": elapsed_milliseconds(started_at),
                    "wait_time_seconds": round(elapsed_milliseconds(started_at) / 1000.0, 2),
                    "report_type": payload.report_type,
                    "provider": provider,
                    "error_kind": classification.kind,
                    "job_id": job.id,
                    "estimated_wait": default_queue_config.estimated_wait_range,
                    "error_reason": str(provider_err)[:80],
                    "variant": ab_variant,
                    "reference": job.id,
                },
            )
            return {
                "status": "queued",
                "action": "report_queued_pending",
                "job_id": job.id,
                "report_id": job.id,
                "reference": job.id,
                "topic": topic,
                "report_type": payload.report_type,
                "estimated_wait": default_queue_config.estimated_wait_range,
                "message": f"Report synthesis request queued ({default_queue_config.estimated_wait_range}).",
                "created_at": job.created_at,
                "degraded": False,
                "error_code": classification.kind,
                "retryable": classification.retryable,
                "retry_after_seconds": classification.retry_after_seconds,
                "is_paid": is_paid_user,
                "priority": 10 if is_paid_user else 0,
            }
    except HTTPException as error:
        detail = error.detail if isinstance(error.detail, dict) else {}
        record_backend_analytics(
            "report_failed",
            user_id,
            {
                "duration_ms": elapsed_milliseconds(started_at),
                "report_type": payload.report_type,
                "error_category": normalized_error_category(error),
                **({"error_kind": str(detail["error_code"])[:60]} if detail.get("error_code") else {}),
                **(scribe_telemetry(scribe) if scribe else {}),
            },
        )
        raise
    except ReportSynthesisError as error:
        logger.warning("Word report failed its synthesis quality gate: %s", error)

        # Classify the error to provide structured response
        provider = getattr(scribe, 'telemetry_last_provider', None) or getattr(scribe, 'provider', 'unknown') if scribe else 'unknown'
        classification = classify_provider_error(error, provider)

        record_backend_analytics(
            "report_failed",
            user_id,
            {
                "duration_ms": elapsed_milliseconds(started_at),
                "report_type": payload.report_type,
                "error_category": "quality_or_provider",
                "error_kind": classification.kind,
                "provider": classification.provider,
                **(scribe_telemetry(scribe) if scribe else {}),
            },
        )

        # Return structured error response
        raise HTTPException(
            status_code=503,
            detail={
                "message": str(error),
                "error_code": classification.kind,
                "provider": classification.provider,
                "retryable": classification.retryable,
                "retry_after_seconds": classification.retry_after_seconds,
                "reference": str(uuid4()),
                "is_paid": entitlements.is_active(user_id),
            }
        ) from error
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
@app.get("/api/reports/cache/{cache_id}")
async def download_cached_research_report(
    cache_id: str,
    report_type: str = "proposal",
    download: bool = False,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    started_at = time.monotonic()
    user = require_supabase_user(authorization)
    user_id = supabase_user_id(user)
    require_api_access(x_api_key)
    if report_type not in {"proposal", "full_starter"}:
        raise HTTPException(status_code=400, detail="Unsupported report type.")
    if not exposure.is_entitled(entitlements, user_id, user.get("email")):
        record_backend_analytics("download_blocked", user_id, {"surface": "cache"})
        raise upgrade_required("word", "Saved reports can be downloaded with a Research Pack.")
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
    
    if download:
        filename = f"{report_type}-report.docx"
        return Response(
            content=document_bytes,
            media_type=DOCX_CONTENT_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return cached_report_response(document_bytes, cache_key, report_type)


@app.get("/v1/reports/cache/{cache_id}/download")
@app.get("/api/reports/cache/{cache_id}/download")
async def download_cached_research_report_file(
    cache_id: str,
    report_type: str = "proposal",
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    return await download_cached_research_report(
        cache_id=cache_id,
        report_type=report_type,
        download=True,
        authorization=authorization,
        x_api_key=x_api_key,
    )


@app.get("/v1/reports/queue")
@app.get("/api/reports/queue")
async def list_report_queue_jobs(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    user_id = supabase_user_id(user)
    require_api_access(x_api_key)
    jobs = global_queue_manager.list_jobs(user_id=user_id)
    return {"jobs": [j.to_dict() for j in jobs]}


@app.get("/v1/reports/queue/{job_id}")
@app.get("/api/reports/queue/{job_id}")
async def get_report_queue_job_status(
    job_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    user_id = supabase_user_id(user)
    require_api_access(x_api_key)
    job = global_queue_manager.get_job(job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Queued report job not found.")
    return job.to_dict()


@app.post("/v1/reports/{job_id}/retry")
@app.post("/api/reports/{job_id}/retry")
async def retry_queued_report(
    job_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    user_id = supabase_user_id(user)
    require_api_access(x_api_key)
    job = global_queue_manager.get_job(job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Queued report job not found.")
    global_queue_manager.retry_job(job_id)
    return {
        "status": "queued",
        "job_id": job.id,
        "topic": job.topic,
        "message": f"Report retry queued ({default_queue_config.estimated_wait_range}).",
        "estimated_wait": default_queue_config.estimated_wait_range,
    }


@app.get("/v1/reports/{job_id}/status")
@app.get("/api/reports/{job_id}/status")
async def get_report_job_status_alias(
    job_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    return await get_report_queue_job_status(job_id=job_id, authorization=authorization, x_api_key=x_api_key)


@app.get("/v1/reports/{job_id}/download")
@app.get("/api/reports/{job_id}/download")
async def download_report_job_alias(
    job_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    return await download_ready_queued_report(job_id=job_id, authorization=authorization, x_api_key=x_api_key)


@app.get("/v1/reports/queue/{job_id}/download")
@app.get("/api/reports/queue/{job_id}/download")
async def download_ready_queued_report(
    job_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    user_id = supabase_user_id(user)
    require_api_access(x_api_key)
    job = global_queue_manager.get_job(job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Queued report job not found.")
    if not exposure.is_entitled(entitlements, user_id, user.get("email")):
        record_backend_analytics("download_blocked", user_id, {"surface": "queue"})
        raise upgrade_required("word", "Queued reports can be downloaded with a Research Pack.")
    if job.status != "ready" or not job.document_base64:
        raise HTTPException(status_code=400, detail=f"Report is not ready for download (current status: {job.status}).")
    doc_bytes = base64.b64decode(job.document_base64)
    filename = job.document_name or f"{job.report_type}-report.docx"
    return Response(
        content=doc_bytes,
        media_type=DOCX_CONTENT_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/v1/notifications")
@app.get("/api/notifications")
async def list_user_notifications(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    user_id = supabase_user_id(user)
    require_api_access(x_api_key)
    notifications = NotificationService.get_user_notifications(user_id)
    return {"notifications": notifications}


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
        result_data = dict(result_data)
        result_data.pop("excel_dossier_storage_path", None)
        # The stored run is complete; free users read the same limited view they got from the scan.
        record["result"] = exposure.results_for(
            result_data, exposure.is_entitled(entitlements, supabase_user_id(user), user.get("email"))
        )
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
        client_source = event.source if event.source in (WEB, EXTENSION) else CLIENT
        analytics.record(
            event_name=event.event,
            user_id=supabase_user_id(user),
            session_id=event.session_id or "unknown",
            properties=build_properties(
                event.event, privacy_safe_analytics_context(event.context), client_source
            ),
            occurred_at=event.timestamp,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception:
        logger.exception("Could not persist client analytics event %s.", event.event)
        return {"status": "accepted"}
    return {"status": "logged"}


@app.post("/v1/feedback")
@app.post("/api/feedback")
async def submit_report_feedback(
    payload: FeedbackRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    record_backend_analytics(
        "feedback_submitted",
        supabase_user_id(user),
        {
            "reference_id": payload.reference,
            "rating": payload.rating,
            "reasons": ",".join(sorted(set(payload.reasons))),
            "report_type": payload.report_type,
        },
    )
    return {"status": "recorded"}


@app.get("/v1/admin/analytics")
async def get_admin_analytics(days: int = 30, x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    return analytics.summary(days=days)


@app.get("/v1/analytics/ab-conversion")
@app.get("/api/analytics/ab-conversion")
async def get_ab_conversion_analytics(days: int = 30, x_admin_token: Optional[str] = Header(None)):
    """Returns side-by-side A/B conversion metrics and aha moment timings."""
    require_admin(x_admin_token)
    return analytics.ab_conversion_metrics(days=days)


def _bounded_days(days: int) -> int:
    return min(max(int(days), 1), 180)


def _build_scorecard(days: int, only: Optional[str] = None) -> Dict[str, Any]:
    rows = analytics.fetch_events(days=days * 2)
    return metrics_engine.scorecard(rows, days, only=only, truncated=len(rows) >= MAX_FETCHED_EVENTS)


ADMIN_UI_DIR = Path(__file__).resolve().parent / "app" / "admin_ui"
ADMIN_UI_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "X-Robots-Tag": "noindex",
    "Referrer-Policy": "no-referrer",
}


def _admin_asset(filename: str, media_type: str) -> FileResponse:
    return FileResponse(ADMIN_UI_DIR / filename, media_type=media_type, headers=ADMIN_UI_HEADERS)


@app.get("/admin", include_in_schema=False)
@app.get("/admin/", include_in_schema=False)
async def admin_dashboard():
    """The static dashboard shell. It holds no data: every figure comes from the token-guarded API."""
    return _admin_asset("index.html", "text/html")


@app.get("/admin/admin.js", include_in_schema=False)
async def admin_dashboard_script():
    return _admin_asset("admin.js", "application/javascript")


@app.get("/admin/admin.css", include_in_schema=False)
async def admin_dashboard_styles():
    return _admin_asset("admin.css", "text/css")


@app.get("/v1/admin/metrics")
async def get_admin_metrics(days: int = 30, x_admin_token: Optional[str] = Header(None)):
    """Scorecard of every registered metric for the window, compared with the previous window."""
    require_admin(x_admin_token)
    return await run_in_threadpool(_build_scorecard, _bounded_days(days))


@app.get("/v1/admin/metrics/{metric_id}")
async def get_admin_metric_detail(metric_id: str, days: int = 30, x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    if metric_id not in metrics_engine.REGISTRY:
        raise HTTPException(status_code=404, detail="Unknown metric.")
    card = await run_in_threadpool(_build_scorecard, _bounded_days(days), metric_id)
    return card["categories"][0]["metrics"][0] | {
        "window_days": card["window_days"], "data_truncated": card["data_truncated"],
    }


@app.get("/v1/admin/health")
async def get_admin_instrumentation_health(days: int = 7, x_admin_token: Optional[str] = Header(None)):
    require_admin(x_admin_token)
    window = _bounded_days(days)
    rows = await run_in_threadpool(analytics.fetch_events, window)
    return instrumentation_health(rows, window)


@app.get("/v1/admin/trace/{request_id}")
async def get_admin_trace(request_id: str, x_admin_token: Optional[str] = Header(None)):
    """Every event recorded for one request, oldest first. Users quote this as their Reference ID."""
    require_admin(x_admin_token)
    try:
        rows = await run_in_threadpool(analytics.fetch_events, 30, None, MAX_FETCHED_EVENTS, request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request id.")
    if not rows:
        raise HTTPException(status_code=404, detail="No events recorded for that request id.")
    timeline = [
        {"event": row["event_name"], "at": row["occurred_at"],
         "source": schema_event_source(row["properties"], row["session_id"]), "properties": row["properties"]}
        for row in rows
    ]
    calls = [item["properties"] for item in timeline if item["event"] == "llm_call"]
    return {
        "request_id": request_id,
        "timeline": timeline,
        "summary": {
            "events": len(timeline),
            "llm_calls": len(calls),
            "input_tokens": sum(c.get("input_tokens") or 0 for c in calls),
            "output_tokens": sum(c.get("output_tokens") or 0 for c in calls),
            "spans": {i["properties"]["name"]: i["properties"]["duration_ms"]
                      for i in timeline if i["event"] == "span" and "name" in i["properties"]},
        },
    }


@app.post("/v1/bundles/purchase")
async def purchase_review_bundle(
    payload: PayPalCaptureRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_admin_token: Optional[str] = Header(None),
):
    """Admin-only: award a bundle to a user (development/testing only)."""
    require_admin(x_admin_token)  # Prevents unauthorized bundle crediting
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    user_id = supabase_user_id(user)
    cfg = default_pricing_config
    bundle_id = payload.bundle_id or cfg.bundle_id
    ab_variant = payload.variant or ExperimentService.get_variant_for_user(user_id)

    entitlements.credit_bundle(user_id, bundle_id, cfg.bundle_query_allowance)
    record_backend_analytics(
        "bundle_purchased",
        user_id,
        {
            "bundle_id": bundle_id,
            "price": cfg.bundle_price_usd,
            "variant": ab_variant,
        },
    )
    return {
        "status": "success",
        "message": f"Successfully purchased {cfg.bundle_name}.",
        "bundle_id": bundle_id,
        "queries_remaining": cfg.bundle_query_allowance,
        "price_paid": cfg.bundle_price_usd,
    }


def record_payment_completed(user_id: str, result) -> None:
    """Revenue events for a pack that was credited just now (never for a replay)."""
    if not result.credited_now or result.pack is None:
        return
    record_backend_analytics("payment_completed", user_id, {
        "provider": "paypal", "plan": result.pack.id, "payment_type": "pack",
        "order_id": result.order["order_id"], "price": float(result.order["amount"]),
    })
    record_backend_analytics("bundle_purchased", user_id, {
        "bundle_id": result.pack.id, "price": float(result.order["amount"]),
        "variant": ExperimentService.get_variant_for_user(user_id),
    })


WORD_PREVIEW_FEATURE = "word_preview"


def release_preview_credit(user_id: str, claimed: bool) -> None:
    """Give the free preview back when generation failed before anything was delivered."""
    if not claimed:
        return
    try:
        entitlements.release_feature_use(user_id, WORD_PREVIEW_FEATURE)
    except Exception:
        logger.exception("Could not release the free preview credit for user %s.", user_id)


def snapshot_response(
    user_id: str,
    document_bytes: bytes,
    report_type: str,
    reference: str,
    cache_hit: bool,
    generation_mode: str,
) -> Dict[str, Any]:
    """What a free user gets instead of the document: its outline and opening paragraph."""
    snapshot = snapshot_from_docx(document_bytes)
    record_backend_analytics(
        "snapshot_served", user_id,
        {"surface": "word", "cache_hit": cache_hit, "locked_sections": snapshot["locked_sections"]},
    )
    return {
        "status": "snapshot",
        "action": "snapshot_ready",
        "report_type": report_type,
        "snapshot": snapshot,
        "generation_mode": generation_mode,
        "degraded": generation_mode != AI_SYNTHESIZED,
        "cache_hit": cache_hit,
        "reference": reference,
    }


def load_run_included_sources(user_id: str, run_id: UUID) -> List[Dict[str, Any]]:
    """The full included-source list of one of the user's own saved scans."""
    rows = require_supabase_database().request(
        "GET",
        "research_runs",
        params={"id": f"eq.{run_id}", "user_id": f"eq.{user_id}", "select": "result", "limit": 1},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Research run not found.")
    included = (rows[0].get("result") or {}).get("included")
    return [dict(source) for source in included if isinstance(source, dict)] if isinstance(included, list) else []


def upgrade_required(surface: str, message: str) -> HTTPException:
    """The one answer a free user gets when a file or full result needs a pack."""
    return HTTPException(
        status_code=403,
        detail={"message": message, "error_code": "upgrade_required", "surface": surface, "requires_bundle": True},
    )


def _plan_summary(user_id: str, record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """What the user bought, for the "Your plan" panel. None when they hold no pack."""
    if not record or record.get("bundle_queries_remaining") is None:
        return None
    try:
        orders = entitlements.purchase_summary(user_id)
    except (RuntimeError, SupabaseRequestError) as error:
        logger.warning("Plan summary unavailable: %s", error)
        return None
    packs = [pack for pack in (get_pack(order["pack_id"]) for order in orders) if pack]
    if not packs:
        return None
    remaining = int(record["bundle_queries_remaining"])
    return {
        "pack_id": packs[0].id,
        "pack_name": packs[0].name,
        "scans_purchased": max(sum(pack.scans for pack in packs), remaining),
        "last_purchased_at": orders[0]["credited_at"],
        "packs": [{"name": pack.name, "scans": pack.scans} for pack in packs],
    }


def _entitlement_view(user_id: str, user_email: Optional[str]) -> Dict[str, Any]:
    record = entitlements.get(user_id)
    return {
        "active": entitlements.is_active(user_id, user_email=user_email),
        "scans_remaining": record.get("bundle_queries_remaining") if record else None,
        "ends_at": record.get("ends_at") if record else None,
        "plan": _plan_summary(user_id, record),
    }


def _checkout_failure(error: Exception, user_id: str, stage: str) -> HTTPException:
    """Map a checkout failure to an honest HTTP error and a payment_failed event."""
    if isinstance(error, CheckoutError):
        code, status = error.code, error.status_code
        detail = {"error_code": error.code, "message": error.message}
    elif isinstance(error, PayPalError):
        code, status = "PAYPAL_API_ERROR", 502
        detail = {"error_code": "paypal_error", "message": "PayPal could not complete this request. Please try again."}
        logger.error("PayPal %s failed: %s", stage, error)
    else:
        code, status = "PAYMENTS_UNAVAILABLE", 503
        detail = {"error_code": "payments_unavailable", "message": "Payments are temporarily unavailable. Please try again shortly."}
        logger.error("Payments %s unavailable: %s", stage, error)
    record_backend_analytics("payment_failed", user_id, {"provider": "paypal", "error_code": code})
    return HTTPException(status_code=status, detail=detail)


@app.get("/v1/checkout/pack")
async def get_checkout_pack():
    """The default pack. Kept for older clients; newer ones read the full list from /packs."""
    return get_pack(None).public()


@app.get("/v1/checkout/packs")
async def get_checkout_packs():
    """Every pack on sale, in display order. Public: it is the same price list the buyer sees."""
    return {"packs": [pack.public() for pack in all_packs()], "default": get_pack(None).id}


@app.post("/v1/checkout/orders")
async def create_checkout_order(
    payload: CheckoutOrderRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    """Start a pack purchase. The price comes from the server's catalog; the client names only a pack."""
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    user_id = supabase_user_id(user)
    try:
        checkout = await run_in_threadpool(create_pack_checkout, paypal, entitlements, user_id, payload.pack_id)
    except (CheckoutError, RuntimeError, ValueError, SupabaseRequestError) as error:
        raise _checkout_failure(error, user_id, "order creation") from error
    record_backend_analytics("checkout_started", user_id, {
        "provider": "paypal", "plan": checkout["pack"]["id"], "payment_type": "pack",
        "order_id": checkout["order_id"],
    })
    return checkout


@app.post("/v1/checkout/orders/{order_id}/capture")
async def capture_checkout_order(
    order_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
):
    """Finish a purchase after the buyer approved it on PayPal. Safe to call again: it credits once."""
    user = require_supabase_user(authorization)
    require_api_access(x_api_key)
    user_id = supabase_user_id(user)
    try:
        result = await run_in_threadpool(capture_pack_order, paypal, entitlements, user_id, order_id)
    except (CheckoutError, RuntimeError, ValueError, SupabaseRequestError) as error:
        raise _checkout_failure(error, user_id, "capture") from error
    record_payment_completed(user_id, result)
    return {
        "status": result.status,
        "pack": result.pack.public() if result.pack else None,
        "entitlement": _entitlement_view(user_id, user.get("email")),
    }


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
    user_email = user.get("email")
    is_user_active = entitlements.is_active(str(user["id"]), user_email=user_email)
    record = entitlements.get(str(user["id"]))
    return {
        "user_id": user_id,
        "active": is_user_active,
        "entitlement": record,
        "scans_remaining": record.get("bundle_queries_remaining") if record else None,
        "ends_at": record.get("ends_at") if record else None,
        "plan": _plan_summary(str(user["id"]), record),
    }


@app.post("/v1/paypal/webhook")
async def paypal_webhook(request: Request):
    event = await request.json()
    headers = {key.upper(): value for key, value in request.headers.items()}
    try:
        verified = await run_in_threadpool(paypal.verify_webhook_signature, headers, event)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error))
    if not verified:
        raise HTTPException(status_code=400, detail="Invalid PayPal webhook signature.")

    event_id = event.get("id")
    if not event_id:
        raise HTTPException(status_code=400, detail="Webhook event has no id.")
    event_type = str(event.get("event_type") or "")[:80]
    provider_id = str((event.get("resource") or {}).get("id") or "")[:80]

    try:
        if not await run_in_threadpool(entitlements.begin_event, event_id):
            return {"status": "already_processed"}
        result = await run_in_threadpool(handle_paypal_event, paypal, entitlements, event)
        await run_in_threadpool(entitlements.finish_event, event_id)
    except CheckoutError as error:
        # A business-rule rejection (for example an amount mismatch): retrying cannot fix it.
        logger.error("PayPal event %s rejected: %s", event_id, error.message)
        await run_in_threadpool(entitlements.finish_event, event_id)
        record_backend_analytics("paypal_webhook_received", "anonymous",
                                 {"event_type": event_type, "provider_id": provider_id, "status": error.code})
        return {"status": "rejected", "code": error.code}
    except Exception:
        # Not marked as processed, so PayPal's retry will run it again.
        logger.exception("PayPal event %s failed and will be retried.", event_id)
        raise HTTPException(status_code=500, detail="Webhook processing failed.")

    user_id = result.order["user_id"] if result.order else "anonymous"
    record_payment_completed(user_id, result)
    record_backend_analytics("paypal_webhook_received", user_id,
                             {"event_type": event_type, "provider_id": provider_id, "status": result.status})
    return {"status": "processed", "outcome": result.status}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("cloud_app.py", host="0.0.0.0", port=8000, reload=True)
