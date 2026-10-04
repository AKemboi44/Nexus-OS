"""Event schema registry: one entry per event; drives validation, tagging and the metric catalog.

Adding an event is one `register(...)` call. Privacy rule for every event: numbers, booleans,
enums and ids only. Never prompts, abstracts, titles, draft text or free-form messages.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from app.analytics.context import app_version, current_request_id

SCHEMA_VERSION = 1
SERVER, WEB, EXTENSION = "server", "web", "extension"
CLIENT = "client"  # legacy rows / builds that do not say which client they are
STAGES = ("acquisition", "activation", "value", "quality", "monetization", "system")


@dataclass(frozen=True)
class Prop:
    kind: str  # "str" | "int" | "float" | "bool" | "any"
    required: bool = False
    values: Tuple[str, ...] = ()


def text(*values: str, required: bool = False) -> Prop:
    return Prop("str", required, tuple(values))


def integer(required: bool = False) -> Prop:
    return Prop("int", required)


def number(required: bool = False) -> Prop:
    return Prop("float", required)


def flag(required: bool = False) -> Prop:
    return Prop("bool", required)


def scalar(required: bool = False) -> Prop:
    return Prop("any", required)


@dataclass(frozen=True)
class EventSpec:
    name: str
    stage: str
    sources: Tuple[str, ...]
    props: Mapping[str, Prop] = field(default_factory=dict)
    description: str = ""


REGISTRY: Dict[str, EventSpec] = {}


def register(
    name: str,
    stage: str,
    sources: Tuple[str, ...],
    props: Optional[Mapping[str, Prop]] = None,
    description: str = "",
) -> EventSpec:
    if stage not in STAGES:
        raise ValueError(f"Unknown stage {stage!r} for event {name!r}.")
    if name in REGISTRY:
        raise ValueError(f"Event {name!r} is already registered.")
    spec = EventSpec(name, stage, tuple(sources), dict(props or {}), description)
    REGISTRY[name] = spec
    return spec


def get(name: str) -> Optional[EventSpec]:
    return REGISTRY.get(name)


def _type_ok(prop: Prop, value: Any) -> bool:
    if value is None:
        return not prop.required
    if prop.kind == "any":
        return isinstance(value, (str, int, float, bool))
    if prop.kind == "bool":
        return isinstance(value, bool)
    if prop.kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if prop.kind == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if prop.kind == "str":
        return isinstance(value, str) and (not prop.values or value in prop.values)
    return False


def validate(name: str, properties: Mapping[str, Any], source: str = SERVER) -> List[str]:
    """Return a list of problem codes (empty when the event conforms to its spec)."""
    spec = REGISTRY.get(name)
    if spec is None:
        return ["unregistered_event"]
    problems: List[str] = []
    if source != CLIENT and source not in spec.sources:
        problems.append(f"unexpected_source:{source}")
    for key, value in properties.items():
        prop = spec.props.get(key)
        if prop is None:
            problems.append(f"unknown_prop:{key}")
        elif not _type_ok(prop, value):
            problems.append(f"bad_type:{key}")
    for key, prop in spec.props.items():
        if prop.required and properties.get(key) is None:
            problems.append(f"missing_prop:{key}")
    return problems


def build_properties(
    event_name: str,
    properties: Optional[Mapping[str, Any]],
    source: str,
    request_id: Optional[str] = None,
    experiments: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Merge caller properties with the envelope; tag (never reject) schema problems."""
    merged = dict(properties or {})
    problems = validate(event_name, merged, source)
    merged["source"] = source
    merged["schema_v"] = SCHEMA_VERSION
    request_id = request_id or current_request_id()
    if request_id:
        merged["request_id"] = request_id
    version = app_version()
    if version:
        merged["app_version"] = version
    if experiments:
        merged["exp"] = dict(experiments)
    if problems == ["unregistered_event"]:
        merged["_unregistered"] = True
    elif problems:
        merged["_schema_problems"] = problems[:10]
    return merged


def event_source(properties: Mapping[str, Any], session_id: Optional[str]) -> str:
    """Source of a stored event, inferring it for rows written before the envelope existed."""
    declared = properties.get("source")
    if declared:
        return str(declared)
    return SERVER if session_id == "backend" else CLIENT


# --- Registry: events emitted today -------------------------------------------------------

_SERVER = (SERVER,)
_BOTH_CLIENTS = (WEB, EXTENSION)

register("workspace_opened", "acquisition", _BOTH_CLIENTS, description="User opened the app.")
register(
    "query_submitted", "activation", _SERVER,
    {"run_id": text(), "tier": text(), "source_cap": scalar(), "variant": text()},
)
register(
    "scan_started", "activation", _SERVER,
    {
        "run_id": text(), "requested_count": integer(), "uploaded_source_count": integer(),
        "inclusion_rule_count": integer(), "domain_category": text(), "variant": text(),
        "topic_corrected": flag(),
    },
)
register(
    "scan_completed", "value", _SERVER,
    {
        "run_id": text(), "duration_ms": integer(), "requested_count": integer(),
        "included_count": integer(), "excluded_count": integer(), "variant": text(),
        "reviewed_count": integer(), "metadata_complete_count": integer(),
    },
)
register(
    "scan_failed", "quality", _SERVER,
    {"run_id": text(), "duration_ms": integer(), "error_category": text(), "variant": text()},
)
register(
    "excel_export_completed", "value", _SERVER,
    {
        "run_id": text(), "duration_ms": integer(), "included_count": integer(),
        "excluded_count": integer(), "cache_hit": flag(), "outcome_category": text(), "variant": text(),
    },
)
register(
    "excel_download_completed", "value", _SERVER,
    {"duration_ms": integer(), "cache_hit": flag(), "outcome_category": text(), "quota_limited": flag()},
)
register(
    "excel_download_failed", "quality", _SERVER,
    {"duration_ms": integer(), "cache_hit": flag(), "error_category": text()},
)
register(
    "report_started", "activation", _SERVER,
    {
        "report_type": text("proposal", "full_starter"), "included_source_count": integer(),
        "uploaded_source_count": integer(), "domain_category": text(), "topic_hash": text(),
    },
)
register(
    "report_completed", "value", _SERVER,
    {
        "report_type": text("proposal", "full_starter"), "duration_ms": integer(), "cache_hit": flag(),
        "included_source_count": integer(), "word_count": integer(), "quality_available": flag(),
        "quality_passed": flag(), "outcome_category": text(), "provider_attempt_count": integer(),
        "provider_fallback_used": flag(), "validation_correction_used": flag(),
        "provider_selected": text(), "model_selected": text(), "degraded_mode": flag(),
        "configured_output_token_limit": integer(),
    },
)
register(
    "report_failed", "quality", _SERVER,
    {
        "report_type": text("proposal", "full_starter"), "duration_ms": integer(),
        "error_category": text(), "error_kind": text(), "provider": text(),
        "provider_attempt_count": integer(), "provider_fallback_used": flag(),
        "validation_correction_used": flag(), "provider_selected": text(), "model_selected": text(),
        "degraded_mode": flag(), "configured_output_token_limit": integer(),
    },
)
register(
    "report_queued", "quality", _SERVER,
    {
        "report_type": text("proposal", "full_starter"), "duration_ms": integer(),
        "wait_time_seconds": number(), "provider": text(), "error_kind": text(),
        "error_reason": text(), "estimated_wait": scalar(), "job_id": text(), "reference": text(),
        "variant": text(),
    },
)
register(
    "report_cache_redownload_completed", "value", _SERVER,
    {"report_type": text(), "duration_ms": integer(), "cache_hit": flag(), "outcome_category": text()},
)
register(
    "report_cache_redownload_failed", "quality", _SERVER,
    {"report_type": text(), "duration_ms": integer(), "error_category": text()},
)
register(
    "second_query_attempted", "monetization", _SERVER,
    {"run_id": text(), "tier": text(), "is_blocked": flag(), "variant": text()},
)
register(
    "paywall_shown", "monetization", _SERVER,
    {"run_id": text(), "context": text(), "copy_variant": text(), "variant": text()},
)
register(
    "results_viewed", "value", _BOTH_CLIENTS,
    {"run_id": text(), "included_count": integer(), "excluded_count": integer(), "from_cache": flag(),
     "variant": text()},
    "User saw the scan results.",
)
register(
    "exclusion_row_opened", "value", _BOTH_CLIENTS,
    {"source_id": text(), "is_excluded_row": flag(), "variant": text()},
)
register(
    "checkout_started", "monetization", _SERVER,
    {"provider": text(), "plan": text(), "payment_type": text(), "order_id": text(),
     "subscription_id": text()},
)
register(
    "paypal_approval_opened", "monetization", _BOTH_CLIENTS,
    {"plan": text(), "order_id": text()},
)
register(
    "payment_failed", "monetization", (SERVER, EXTENSION, WEB),
    {"provider": text(), "error_code": text(), "order_id": text()},
)
register(
    "paypal_webhook_received", "monetization", _SERVER,
    {"event_type": text(), "provider_id": text(), "status": text()},
)
register(
    "bundle_purchased", "monetization", _SERVER,
    {"bundle_id": text(), "price": number(), "variant": text()},
)
register(
    "deliverable_clicked", "activation", _BOTH_CLIENTS,
    {"kind": text("excel", "proposal", "full_starter", required=True)},
    "User asked for a deliverable (Excel dossier or Word report).",
)
register(
    "error_displayed", "quality", _BOTH_CLIENTS,
    {"surface": text("scan", "report", "download", "payment"), "error_code": text(required=True),
     "status_code": integer(), "reference_id": text()},
    "An error message was shown to the user.",
)

# --- Registry: instrumentation V1 events (tracing, quality, feedback) ----------------------

register(
    "span", "system", _SERVER,
    {
        "name": text(required=True), "duration_ms": integer(required=True),
        "outcome": text("ok", "error"), "report_type": text(), "cache_hit": flag(),
    },
    "A timed section of a request (scan.discovery, report.synthesis, ...).",
)
register(
    "llm_call", "system", _SERVER,
    {
        "purpose": text(required=True), "provider": text(), "model": text(), "attempt": integer(),
        "outcome": text("ok", "provider_error", "invalid_output", "quality_gate"),
        "latency_ms": integer(), "input_tokens": integer(), "output_tokens": integer(),
        "http_status": integer(), "error_kind": text(),
    },
    "One model call. Tokens are billed even when the output is unusable.",
)
register(
    "proposal_quality", "quality", _SERVER,
    {
        "generation_mode": text("ai_synthesized", "template_fallback", required=True),
        "synthesis_failure": text("not_configured", "provider_error", "invalid_output", "quality_gate"),
        "attempts": integer(), "repair_used": flag(), "word_count": integer(),
        "source_count": integer(), "cited_source_count": integer(), "integrative_paragraphs": integer(),
        "gate_errors": text(),
    },
    "How a proposal was produced and how it scored against the quality gate.",
)
register(
    "feedback_submitted", "quality", _SERVER,
    {
        "reference_id": text(required=True), "rating": text("up", "down", required=True),
        "reasons": text(), "report_type": text("proposal", "full_starter"),
    },
    "User rating of a delivered report; reference_id is the report's request id.",
)
