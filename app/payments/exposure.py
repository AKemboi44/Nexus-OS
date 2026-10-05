"""What a free user is allowed to see and take away.

Free users get totals plus a few real rows, never the full evidence set or any file. The limit is
applied to responses only: the stored research run stays complete, so buying a pack unlocks the same
run without a new scan. Everything is a whitelist, so a field added to the pipeline later is hidden
from free users until someone decides to show it.
"""

import os
from typing import Any, Dict, List, Optional

from app.payments.config import default_pricing_config

PREVIEW_ROWS = 3

RESULT_KEYS = (
    "query", "status", "domain_executed", "discovery_report_name", "inclusion_reasons",
    "ab_variant", "is_paid_user", "queries_remaining", "free_allowance", "requires_paywall",
    "paywall_copy", "dossier_download", "research_run_id", "saved_dossier_id", "criteria",
)
SOURCE_KEYS = (
    "uid", "title", "authors", "venue", "year", "doi", "url", "citation_count", "is_peer_reviewed",
    "provider_source", "domain", "inclusion_reason", "exclusion_reason", "criteria_result", "criteria_not_met",
)


def is_entitled(entitlements, user_id: str, email: Optional[str] = None) -> bool:
    """True when the user may see full results and download files (pack, whitelist, or pricing off)."""
    if not default_pricing_config.pricing_model_enabled:
        return True
    whitelist = default_pricing_config.whitelisted_emails
    if str(email or "").strip().lower() in whitelist or str(user_id or "").strip().lower() in whitelist:
        return True
    try:
        return bool(entitlements.is_active(user_id, user_email=email))
    except TypeError:
        return bool(entitlements.is_active(user_id))


def free_dossier_downloads() -> int:
    """How many Excel downloads a free user gets. Zero: the dossier is a paid file."""
    try:
        return max(0, int(os.getenv("NEXUS_FREE_DOSSIER_DOWNLOADS", "0")))
    except ValueError:
        return 0


def free_word_previews() -> int:
    """How many Word snapshots a free user gets per month."""
    try:
        return max(0, int(os.getenv("NEXUS_FREE_WORD_PREVIEWS", "1")))
    except ValueError:
        return 1


def _sources(result: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = result.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def with_counts(result: Dict[str, Any]) -> Dict[str, Any]:
    """Totals computed from the full lists, so clients never derive them from a truncated list."""
    included, excluded = len(_sources(result, "included")), len(_sources(result, "excluded"))
    return {**result, "counts": {"included": included, "excluded": excluded, "reviewed": included + excluded}}


def preview_view(result: Dict[str, Any]) -> Dict[str, Any]:
    """The free-tier view of a research result: totals, the first few rows, and what is locked."""
    included, excluded = _sources(result, "included"), _sources(result, "excluded")
    shown_included, shown_excluded = included[:PREVIEW_ROWS], excluded[:PREVIEW_ROWS]

    def trim(source: Dict[str, Any]) -> Dict[str, Any]:
        return {key: source[key] for key in SOURCE_KEYS if key in source}

    view = {key: result[key] for key in RESULT_KEYS if key in result}
    view["included"] = [trim(source) for source in shown_included]
    view["excluded"] = [trim(source) for source in shown_excluded]
    view["counts"] = {"included": len(included), "excluded": len(excluded), "reviewed": len(included) + len(excluded)}
    view["locked"] = {
        "included_hidden": len(included) - len(shown_included),
        "excluded_hidden": len(excluded) - len(shown_excluded),
    }
    view["preview"] = True
    if free_dossier_downloads() == 0:
        view["dossier_download"] = {"unlimited": False, "limit": 0, "used": 0, "remaining": 0}
    return view


def results_for(result: Dict[str, Any], entitled: bool) -> Dict[str, Any]:
    return with_counts(result) if entitled else preview_view(result)
