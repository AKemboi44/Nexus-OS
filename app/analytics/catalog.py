"""V1 metric catalog. One decorated function per metric; see metrics_engine.metric.

Conventions: outcome metrics read server events (clients re-emit some); zero denominators give
"no data" (None), never 0%. Targets are initial guesses to tune once real traffic exists.
"""

import json
import os
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Dict, List, Optional

from app.analytics.metrics_engine import (
    Measurement, MetricContext, mean, median, metric, percentile, rate,
)

CX, PE, QUALITY, RELIABILITY, MONEY, DATA = (
    "customer_experience", "product_effectiveness", "quality", "reliability_cost", "monetization", "data_quality",
)
DELIVERABLES = ("excel_download_completed", "report_completed")
LLM_OUTCOMES_WITH_OUTPUT = ("ok", "quality_gate")
ORPHAN_GRACE = timedelta(minutes=10)
REGENERATE_WINDOW = timedelta(hours=1)
DEFAULT_PRICES = {"claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0}}  # USD per million tokens


def price_table() -> Dict[str, Dict[str, float]]:
    raw = os.getenv("LLM_PRICES_JSON")
    if not raw:
        return DEFAULT_PRICES
    try:
        table = json.loads(raw)
        return {m: {"input": float(p["input"]), "output": float(p["output"])} for m, p in table.items()}
    except (ValueError, KeyError, TypeError, AttributeError):
        return DEFAULT_PRICES


def _counts(items) -> Dict[str, int]:
    return dict(Counter(item for item in items if item).most_common())


def _numbers(events, key: str) -> List[float]:
    return [value for value in (e.number(key) for e in events) if value is not None]


def _latest_feedback(ctx: MetricContext):
    """Latest rating per (user, report): a user changing their mind counts once."""
    latest = {}
    for event in ctx.of("feedback_submitted"):
        latest[(event.user, event.props.get("reference_id"))] = event
    return latest


def _first_deliverable_after(ctx: MetricContext, user: str, after) -> Optional[object]:
    times = [e.at for name in DELIVERABLES for e in ctx.of(name) if e.user == user and e.at >= after]
    return min(times) if times else None


# --- Customer experience ---------------------------------------------------------------

@metric("scan_success_rate", "Scan success rate", CX, "rate", "Started scans that completed.",
        good="up", target=0.95)
def scan_success_rate(ctx):
    started = {e.props.get("run_id") for e in ctx.of("scan_started")} - {None}
    completed = {e.props.get("run_id") for e in ctx.of("scan_completed")} - {None}
    done = len(started & completed)
    return Measurement(rate(done, len(started)), done, len(started), len(started),
                       {"failed": len(started & ({e.props.get("run_id") for e in ctx.of("scan_failed")} - {None}))})


@metric("scan_latency_p95", "Scan latency (p95)", CX, "ms", "95th percentile time to complete a scan.",
        good="down", target=90_000)
def scan_latency_p95(ctx):
    durations = _numbers(ctx.of("scan_completed"), "duration_ms")
    return Measurement(percentile(durations, 0.95), n=len(durations), breakdown={"p50": median(durations)})


@metric("report_delivered_rate", "Report delivered rate", CX, "rate",
        "Reports requested that ended in a document (AI-written or template).", good="up", target=0.95)
def report_delivered_rate(ctx):
    started, completed = ctx.of("report_started"), ctx.of("report_completed")
    by_type = {
        kind: {"requested": sum(1 for e in started if e.props.get("report_type") == kind),
               "delivered": sum(1 for e in completed if e.props.get("report_type") == kind)}
        for kind in {e.props.get("report_type") for e in started} - {None}
    }
    value = rate(len(completed), len(started))
    return Measurement(None if value is None else min(1.0, value), len(completed), len(started),
                       len(started), by_type)


@metric("report_latency_p95", "Report latency (p95)", CX, "ms",
        "95th percentile time to generate a report (cache hits excluded).", good="down", target=120_000)
def report_latency_p95(ctx):
    fresh = [e for e in ctx.of("report_completed") if not e.props.get("cache_hit")]
    durations = _numbers(fresh, "duration_ms")
    return Measurement(percentile(durations, 0.95), n=len(durations), breakdown={"p50": median(durations)})


@metric("time_to_first_deliverable", "Time to first deliverable", CX, "s",
        "Median seconds from a user's first scan to their first download or report.",
        good="down", target=900, sparkline=False)
def time_to_first_deliverable(ctx):
    gaps = []
    for user, start in ctx.first_by_user("scan_started").items():
        got = _first_deliverable_after(ctx, user, start)
        if got is not None:
            gaps.append((got - start).total_seconds())
    return Measurement(median(gaps), n=len(gaps))


@metric("error_exposure_rate", "Error exposure rate", CX, "rate",
        "Scan, report and download attempts that ended in an error.", good="down", target=0.05)
def error_exposure_rate(ctx):
    failures = ctx.of("scan_failed") + ctx.of("report_failed") + ctx.of("excel_download_failed")
    attempts = (len(ctx.of("scan_started")) + len(ctx.of("report_started"))
                + len(ctx.of("excel_download_completed")) + len(ctx.of("excel_download_failed")))
    return Measurement(rate(len(failures), attempts), len(failures), attempts, attempts,
                       _counts(e.props.get("error_kind") or e.props.get("error_category") for e in failures))


@metric("queued_share", "Reports sent to the queue", CX, "rate",
        "Report requests that had to be queued because the writing service was busy.", good="down", target=0.05)
def queued_share(ctx):
    started = len(ctx.of("report_started"))
    queued = len(ctx.of("report_queued"))
    return Measurement(rate(queued, started), queued, started, started)


@metric("rating_positive_rate", "Reports rated helpful", CX, "rate",
        "Share of rated reports marked helpful (latest rating per user and report).", good="up", target=0.8)
def rating_positive_rate(ctx):
    latest = _latest_feedback(ctx).values()
    up = sum(1 for e in latest if e.props.get("rating") == "up")
    reasons = _counts(r for e in latest if e.props.get("rating") == "down"
                      for r in str(e.props.get("reasons") or "").split(","))
    return Measurement(rate(up, len(latest)), up, len(latest), len(latest), {"down_reasons": reasons})


@metric("rating_response_rate", "Rating response rate", CX, "rate",
        "Delivered reports that received a rating. Low values mean ratings are only directional.")
def rating_response_rate(ctx):
    delivered = [e for e in ctx.of("report_completed") if not e.props.get("cache_hit")]
    rated = len(_latest_feedback(ctx))
    value = rate(rated, len(delivered))
    return Measurement(None if value is None else min(1.0, value), rated, len(delivered), len(delivered))


# --- Product effectiveness --------------------------------------------------------------

@metric("activation_rate", "Activation rate", PE, "rate",
        "Users who got a deliverable (download or report) within 24 hours of their first completed scan.",
        good="up", target=0.5, sparkline=False)
def activation_rate(ctx):
    firsts = ctx.first_by_user("scan_completed")
    activated = 0
    for user, start in firsts.items():
        got = _first_deliverable_after(ctx, user, start)
        if got is not None and got - start <= timedelta(hours=24):
            activated += 1
    return Measurement(rate(activated, len(firsts)), activated, len(firsts), len(firsts))


@metric("funnel_scan_to_report", "Scan to report conversion", PE, "rate",
        "Users with a completed scan who went on to receive a report. Each step counts only users who "
        "also reached every earlier step, so no step can exceed the one before it.", sparkline=False)
def funnel_scan_to_report(ctx):
    stages = [("scan_started", "Scan started"), ("scan_completed", "Scan completed"),
              ("report_started", "Report requested"), ("report_completed", "Report delivered")]
    steps, reached = [], None
    for name, label in stages:
        users = ctx.users(name)
        reached_now = users if reached is None else users & reached
        steps.append({"stage": name, "label": label, "users": len(reached_now),
                      "step_rate": None if reached is None else rate(len(reached_now), len(reached))})
        reached = reached_now
    scanned, delivered = steps[1]["users"], steps[-1]["users"]
    return Measurement(rate(delivered, scanned), delivered, scanned, scanned, steps)


@metric("repeat_use_rate", "Repeat use", PE, "rate",
        "Users active on two or more different days in the window.", sparkline=False)
def repeat_use_rate(ctx):
    days = defaultdict(set)
    for event in ctx.events:
        if event.source == "server" and event.user != "anonymous":
            days[event.user].add(event.at.date())
    repeat = sum(1 for active in days.values() if len(active) >= 2)
    return Measurement(rate(repeat, len(days)), repeat, len(days), len(days))


@metric("zero_result_rate", "Scans with no included sources", PE, "rate",
        "Completed scans where nothing passed the review criteria.", good="down", target=0.05)
def zero_result_rate(ctx):
    scans = ctx.of("scan_completed")
    included = _numbers(scans, "included_count")
    excluded = _numbers(scans, "excluded_count")
    empty = sum(1 for value in included if value == 0)
    total_found = sum(included) + sum(excluded)
    return Measurement(rate(empty, len(included)), empty, len(included), len(included),
                       {"median_included": median(included), "inclusion_rate": rate(sum(included), total_found)})


@metric("metadata_completeness", "Source metadata completeness", PE, "rate",
        "Reviewed sources with title, authors, year and a venue or link.", good="up", target=0.8)
def metadata_completeness(ctx):
    scans = ctx.of("scan_completed")
    complete, reviewed = sum(_numbers(scans, "metadata_complete_count")), sum(_numbers(scans, "reviewed_count"))
    return Measurement(rate(complete, reviewed), complete, reviewed, int(reviewed))


# --- Quality ------------------------------------------------------------------------------

def _proposals(ctx):
    return ctx.of("proposal_quality")


@metric("ai_synthesis_rate", "AI-written proposals", QUALITY, "rate",
        "Proposals written by the model rather than the template fallback.", good="up", target=0.9)
def ai_synthesis_rate(ctx):
    proposals = _proposals(ctx)
    ai = [e for e in proposals if e.props.get("generation_mode") == "ai_synthesized"]
    reasons = _counts(e.props.get("synthesis_failure") for e in proposals
                      if e.props.get("generation_mode") == "template_fallback")
    return Measurement(rate(len(ai), len(proposals)), len(ai), len(proposals), len(proposals),
                       {"fallback_reasons": reasons})


@metric("first_pass_gate_rate", "Drafts accepted first time", QUALITY, "rate",
        "AI drafts that passed the quality gate without a repair attempt.", good="up", target=0.7)
def first_pass_gate_rate(ctx):
    attempted = [e for e in _proposals(ctx) if (e.number("attempts") or 0) >= 1]
    first = [e for e in attempted
             if e.props.get("generation_mode") == "ai_synthesized" and e.number("attempts") == 1]
    repaired = [e for e in attempted if e.number("attempts") == 2]
    repaired_ok = [e for e in repaired if e.props.get("generation_mode") == "ai_synthesized"]
    return Measurement(rate(len(first), len(attempted)), len(first), len(attempted), len(attempted),
                       {"repair_attempts": len(repaired), "repair_successes": len(repaired_ok)})


@metric("citation_coverage", "Citation coverage", QUALITY, "rate",
        "Median share of supplied sources actually cited in an AI-written proposal.", good="up", target=0.8)
def citation_coverage(ctx):
    shares = [cited / total for e in _proposals(ctx)
              if e.props.get("generation_mode") == "ai_synthesized"
              and (total := e.number("source_count")) and (cited := e.number("cited_source_count")) is not None]
    return Measurement(median(shares), n=len(shares), breakdown={"mean": mean(shares)})


@metric("gate_rejection_rate", "Drafts rejected by the quality gate", QUALITY, "rate",
        "Model drafts received that failed the citation, originality or length checks.",
        good="down", target=0.2)
def gate_rejection_rate(ctx):
    received = [e for e in ctx.of("llm_call") if e.props.get("outcome") in LLM_OUTCOMES_WITH_OUTPUT]
    rejected = [e for e in received if e.props.get("outcome") == "quality_gate"]
    codes = _counts(code for e in _proposals(ctx) for code in str(e.props.get("gate_errors") or "").split(","))
    return Measurement(rate(len(rejected), len(received)), len(rejected), len(received), len(received),
                       {"gate_error_codes": codes})


@metric("topic_correction_rate", "Topics auto-corrected", QUALITY, "rate",
        "Scans where the spelling fixer changed the user's topic.")
def topic_correction_rate(ctx):
    scans = [e for e in ctx.of("scan_started") if "topic_corrected" in e.props]
    corrected = sum(1 for e in scans if e.props.get("topic_corrected") is True)
    return Measurement(rate(corrected, len(scans)), corrected, len(scans), len(scans))


@metric("rating_by_mode", "Helpful rate: AI vs template", QUALITY, "rate",
        "Do users rate AI-written proposals higher than template ones? Value is the AI helpful rate.")
def rating_by_mode(ctx):
    mode_of = {e.request_id: e.props.get("generation_mode") for e in _proposals(ctx) if e.request_id}
    tally = {"ai_synthesized": [0, 0], "template_fallback": [0, 0]}
    for event in _latest_feedback(ctx).values():
        mode = mode_of.get(event.props.get("reference_id"))
        if mode in tally:
            tally[mode][1] += 1
            tally[mode][0] += event.props.get("rating") == "up"
    ai_up, ai_total = tally["ai_synthesized"]
    breakdown = {m: {"helpful": up, "rated": total, "rate": rate(up, total)} for m, (up, total) in tally.items()}
    return Measurement(rate(ai_up, ai_total), ai_up, ai_total, ai_total, breakdown)


@metric("regenerate_rate", "Reports regenerated", QUALITY, "rate",
        "Users who requested the same report again within an hour: a dissatisfaction proxy.",
        sparkline=False)
def regenerate_rate(ctx):
    requests = defaultdict(list)
    for event in ctx.of("report_started"):
        if event.props.get("topic_hash"):
            requests[(event.user, event.props["topic_hash"], event.props.get("report_type"))].append(event.at)
    users = {key[0] for key in requests}
    repeaters = {
        key[0] for key, times in requests.items()
        if any(later - earlier <= REGENERATE_WINDOW for earlier, later in zip(times, times[1:]))
    }
    return Measurement(rate(len(repeaters), len(users)), len(repeaters), len(users), len(users))


# --- Reliability and cost -----------------------------------------------------------------

@metric("llm_latency_p95", "Model call latency (p95)", RELIABILITY, "ms",
        "95th percentile latency of model calls, with a per-model breakdown.", good="down", target=60_000)
def llm_latency_p95(ctx):
    calls = ctx.of("llm_call")
    latencies = _numbers(calls, "latency_ms")
    grouped = defaultdict(list)
    for call in calls:
        if (latency := call.number("latency_ms")) is not None:
            grouped[f"{call.props.get('provider')}/{call.props.get('model')}"].append(latency)
    return Measurement(percentile(latencies, 0.95), n=len(latencies), breakdown={
        key: {"n": len(v), "p50": median(v), "p95": percentile(v, 0.95)} for key, v in grouped.items()})


@metric("llm_error_rate", "Model call error rate", RELIABILITY, "rate",
        "Model calls that failed at the provider.", good="down", target=0.05)
def llm_error_rate(ctx):
    calls = ctx.of("llm_call")
    errors = [e for e in calls if e.props.get("outcome") == "provider_error"]
    return Measurement(rate(len(errors), len(calls)), len(errors), len(calls), len(calls),
                       _counts(e.props.get("error_kind") for e in errors))


# Model calls older than the purpose field have none; they were all proposal calls.
PROPOSAL_PURPOSES = {"proposal_synthesis", None}
REVIEW_PURPOSES = {"literature_review"}


def _calls_by_request(ctx, purposes=PROPOSAL_PURPOSES):
    grouped = defaultdict(list)
    for call in ctx.of("llm_call"):
        if call.request_id and call.props.get("purpose") in purposes:
            grouped[call.request_id].append(call)
    return grouped


@metric("tokens_per_proposal", "Tokens per proposal", RELIABILITY, "tokens",
        "Mean input + output tokens across all model calls for one proposal (repairs included).")
def tokens_per_proposal(ctx):
    totals = [(sum(_numbers(calls, "input_tokens")), sum(_numbers(calls, "output_tokens")))
              for calls in _calls_by_request(ctx).values()]
    return Measurement(mean([i + o for i, o in totals]), n=len(totals),
                       breakdown={"mean_input": mean([i for i, _ in totals]),
                                  "mean_output": mean([o for _, o in totals])})


def _request_cost(calls, prices) -> Optional[float]:
    """Model cost of one request, or None when any of its calls used an unpriced model."""
    total = 0.0
    for call in calls:
        price = prices.get(str(call.props.get("model")))
        if price is None:
            return None
        total += ((call.number("input_tokens") or 0) * price["input"]
                  + (call.number("output_tokens") or 0) * price["output"]) / 1_000_000
    return total


def _mean_request_cost(ctx, purposes) -> Measurement:
    prices, costs, unpriced = price_table(), [], 0
    for calls in _calls_by_request(ctx, purposes).values():
        total = _request_cost(calls, prices)
        if total is None:
            unpriced += 1
        else:
            costs.append(total)
    return Measurement(mean(costs), n=len(costs), breakdown={"requests_unpriced": unpriced,
                                                              "total_usd": sum(costs)})


@metric("cost_per_proposal", "Estimated cost per proposal", RELIABILITY, "usd",
        "Mean model cost per proposal from configured prices (LLM_PRICES_JSON). Unpriced models are skipped.")
def cost_per_proposal(ctx):
    return _mean_request_cost(ctx, PROPOSAL_PURPOSES)


@metric("cost_per_literature_review", "Estimated cost per literature review", RELIABILITY, "usd",
        "Mean model cost of one complete literature review (all chunks, retries and fallbacks), from configured prices.")
def cost_per_literature_review(ctx):
    return _mean_request_cost(ctx, REVIEW_PURPOSES)


@metric("cache_hit_rate", "Report cache hit rate", RELIABILITY, "rate",
        "Delivered reports served from cache (no model cost).")
def cache_hit_rate(ctx):
    completed = ctx.of("report_completed")
    hits = sum(1 for e in completed if e.props.get("cache_hit") is True)
    return Measurement(rate(hits, len(completed)), hits, len(completed), len(completed))


# --- Monetization -------------------------------------------------------------------------

@metric("paywall_exposure_rate", "Users who hit the paywall", MONEY, "rate",
        "Users who tried to run a query and were shown the paywall (blocked users never reach "
        "query_submitted, so they are counted through second_query_attempted).")
def paywall_exposure_rate(ctx):
    active = ctx.users("query_submitted", "second_query_attempted")
    shown = ctx.users("paywall_shown") & active
    return Measurement(rate(len(shown), len(active)), len(shown), len(active), len(active))


@metric("upgrade_cta_click_rate", "Users who clicked an upgrade button", MONEY, "rate",
        "Users who ran a scan and then clicked any upgrade button; the breakdown shows clicks per placement.")
def upgrade_cta_click_rate(ctx):
    scanners = ctx.users("scan_started")
    clicks = [e for source in ("web", "extension", "client") for e in ctx.of("upgrade_cta_clicked", source)]
    clickers = {e.user for e in clicks}
    return Measurement(rate(len(clickers & scanners) if scanners else 0, len(scanners)),
                       len(clickers & scanners), len(scanners), len(scanners),
                       {"clicks_by_placement": _counts(e.props.get("placement") for e in clicks),
                        "unique_users_by_placement": {
                            placement: len({e.user for e in clicks if e.props.get("placement") == placement})
                            for placement in {e.props.get("placement") for e in clicks} - {None}}})


@metric("support_chat_rate", "Troubled users who opened support chat", CX, "rate",
        "Users who saw an error or the paywall and then opened the WhatsApp support chat; the breakdown shows "
        "clicks per placement, so you can see where people look for help.", sparkline=False)
def support_chat_rate(ctx):
    clicks = [e for source in ("web", "extension", "client") for e in ctx.of("support_chat_clicked", source)]
    clickers, troubled = {e.user for e in clicks}, ctx.users("error_displayed", "paywall_shown", source=None)
    return Measurement(rate(len(clickers & troubled), len(troubled)), len(clickers & troubled), len(troubled),
                       len(troubled), {"clicks_by_placement": _counts(e.props.get("placement") for e in clicks)})


@metric("cta_to_checkout", "Upgrade click to checkout", MONEY, "rate",
        "Users who clicked an upgrade button and then started a PayPal checkout.", sparkline=False)
def cta_to_checkout(ctx):
    clickers = {e.user for source in ("web", "extension", "client") for e in ctx.of("upgrade_cta_clicked", source)}
    started = ctx.users("checkout_started")
    return Measurement(rate(len(clickers & started), len(clickers)), len(clickers & started), len(clickers),
                       len(clickers))


@metric("paywall_to_checkout", "Paywall to checkout", MONEY, "rate",
        "Users shown the paywall who started checkout.", sparkline=False)
def paywall_to_checkout(ctx):
    shown, started = ctx.users("paywall_shown"), ctx.users("checkout_started")
    return Measurement(rate(len(shown & started), len(shown)), len(shown & started), len(shown), len(shown))


@metric("checkout_to_purchase", "Checkout to purchase", MONEY, "rate",
        "Users who started checkout and completed a purchase.", sparkline=False)
def checkout_to_purchase(ctx):
    started, bought = ctx.users("checkout_started"), ctx.users("bundle_purchased", "payment_completed")
    return Measurement(rate(len(started & bought), len(started)), len(started & bought), len(started),
                       len(started))


@metric("revenue_total", "Pack revenue", MONEY, "usd",
        "Sum of pack purchases in the window; the breakdown shows purchases and revenue per pack.")
def revenue_total(ctx):
    purchases = ctx.of("bundle_purchased")
    by_pack = {}
    for event in purchases:
        pack = by_pack.setdefault(str(event.props.get("bundle_id") or "unknown"), {"purchases": 0, "revenue": 0.0})
        pack["purchases"] += 1
        pack["revenue"] += event.number("price") or 0.0
    return Measurement(sum(_numbers(purchases, "price")) if purchases else None, n=len(purchases),
                       breakdown={"purchases": len(purchases), "by_pack": by_pack})


@metric("snapshot_to_purchase", "Free preview to purchase", MONEY, "rate",
        "Users shown a free preview (results or Word snapshot) who later bought a pack; the breakdown "
        "shows how many users saw each kind of preview.", sparkline=False)
def snapshot_to_purchase(ctx):
    served = ctx.of("snapshot_served")
    seen, bought = {e.user for e in served}, ctx.users("bundle_purchased", "payment_completed")
    converted = seen & bought
    return Measurement(rate(len(converted), len(seen)), len(converted), len(seen), len(seen),
                       {"users_by_surface": {surface: len({e.user for e in served if e.props.get("surface") == surface})
                                             for surface in {e.props.get("surface") for e in served} - {None}}})


@metric("preview_cost_per_purchase", "Free-preview model cost per purchase", MONEY, "usd",
        "Model cost of free Word snapshots (cache hits are free) divided by packs bought in the window, "
        "so the spend on free previews is judged against what they earn.", sparkline=False)
def preview_cost_per_purchase(ctx):
    free_requests = {e.request_id for e in ctx.of("report_completed")
                     if e.props.get("tier") == "free" and e.props.get("cache_hit") is not True and e.request_id}
    prices, spend, unpriced = price_table(), 0.0, 0
    for request_id, calls in _calls_by_request(ctx).items():
        if request_id not in free_requests:
            continue
        cost = _request_cost(calls, prices)
        if cost is None:
            unpriced += 1
        else:
            spend += cost
    purchases = ctx.of("bundle_purchased")
    return Measurement(spend / len(purchases) if purchases and free_requests else None, n=len(purchases),
                       breakdown={"preview_spend_usd": spend, "free_previews": len(free_requests),
                                  "purchases": len(purchases), "requests_unpriced": unpriced,
                                  "revenue": sum(_numbers(purchases, "price"))})


# --- Data quality -------------------------------------------------------------------------

@metric("schema_conformance", "Events matching the schema", DATA, "rate",
        "Server events with no schema problems or unregistered names.", good="up", target=0.99)
def schema_conformance(ctx):
    events = [e for e in ctx.events if e.source == "server"]
    bad = [e for e in events if e.props.get("_unregistered") or e.props.get("_schema_problems")]
    problems = _counts(p for e in bad for p in (e.props.get("_schema_problems") or ["unregistered_event"]))
    return Measurement(rate(len(events) - len(bad), len(events)), len(events) - len(bad), len(events),
                       len(events), {"top_problems": dict(list(problems.items())[:10])})


@metric("orphan_report_rate", "Reports with no outcome", DATA, "rate",
        "Report requests older than 10 minutes with no completed, failed or queued event.",
        good="down", target=0.01)
def orphan_report_rate(ctx):
    outcomes = {e.request_id for name in ("report_completed", "report_failed", "report_queued")
                for e in ctx.of(name) if e.request_id}
    requests = [e for e in ctx.of("report_started") if e.request_id and ctx.now - e.at > ORPHAN_GRACE]
    orphans = [e for e in requests if e.request_id not in outcomes]
    return Measurement(rate(len(orphans), len(requests)), len(orphans), len(requests), len(requests))


@metric("client_coverage", "Scans seen by a client", DATA, "rate",
        "Completed scans whose results a web or extension client also reported viewing. Low means "
        "client instrumentation is missing or blocked.", sparkline=False)
def client_coverage(ctx):
    scans = {e.props.get("run_id") for e in ctx.of("scan_completed")} - {None}
    seen_by = defaultdict(set)
    for source in ("web", "extension", "client"):
        for event in ctx.of("results_viewed", source):
            if event.props.get("run_id") in scans:
                seen_by[source].add(event.props["run_id"])
    seen = set().union(*seen_by.values()) if seen_by else set()
    return Measurement(rate(len(seen), len(scans)), len(seen), len(scans), len(scans),
                       {source: len(runs) for source, runs in seen_by.items()})
