"""Metric engine: a registry of metric functions evaluated over windows of analytics events.

Adding a metric is one decorated function in catalog.py; the API and the /admin UI are generated
from this registry, so neither needs to change.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from app.analytics import schema

CATEGORIES = (
    ("customer_experience", "Customer experience"),
    ("product_effectiveness", "Product effectiveness"),
    ("quality", "Quality"),
    ("reliability_cost", "Reliability and cost"),
    ("monetization", "Monetization"),
    ("data_quality", "Data quality"),
)
SPARKLINE_DAYS = 14


def parse_time(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def rate(numerator: float, denominator: float) -> Optional[float]:
    return numerator / denominator if denominator else None


def percentile(values: Sequence[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower, upper = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def median(values: Sequence[float]) -> Optional[float]:
    return percentile(values, 0.5)


def mean(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


@dataclass
class Event:
    name: str
    user: str
    session: str
    at: datetime
    props: Dict[str, Any]
    source: str

    @property
    def request_id(self) -> Optional[str]:
        return self.props.get("request_id")

    def number(self, key: str) -> Optional[float]:
        value = self.props.get(key)
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def to_events(rows: Iterable[Dict[str, Any]]) -> List[Event]:
    events = []
    for row in rows:
        at = parse_time(row.get("occurred_at"))
        if at is None:
            continue
        props = row.get("properties") if isinstance(row.get("properties"), dict) else {}
        events.append(Event(
            name=row.get("event_name"),
            user=row.get("user_key") or "anonymous",
            session=row.get("session_id") or "unknown",
            at=at,
            props=props,
            source=schema.event_source(props, row.get("session_id")),
        ))
    events.sort(key=lambda event: event.at)
    return events


class MetricContext:
    """Events of one window. Outcome metrics read server events only (clients re-emit some)."""

    def __init__(self, events: List[Event], now: Optional[datetime] = None):
        self.events = events
        self.now = now or datetime.now(timezone.utc)
        self._by_name: Dict[str, List[Event]] = defaultdict(list)
        for event in events:
            self._by_name[event.name].append(event)

    def of(self, name: str, source: Optional[str] = schema.SERVER) -> List[Event]:
        found = self._by_name.get(name, [])
        return [e for e in found if e.source == source] if source else list(found)

    def users(self, *names: str, source: Optional[str] = schema.SERVER) -> set:
        return {e.user for name in names for e in self.of(name, source)}

    def first_by_user(self, *names: str, source: Optional[str] = schema.SERVER) -> Dict[str, datetime]:
        first: Dict[str, datetime] = {}
        for name in names:
            for event in self.of(name, source):
                if event.user not in first or event.at < first[event.user]:
                    first[event.user] = event.at
        return first

    def by_day(self) -> Dict[str, "MetricContext"]:
        days: Dict[str, List[Event]] = defaultdict(list)
        for event in self.events:
            days[event.at.date().isoformat()].append(event)
        return {day: MetricContext(items, self.now) for day, items in days.items()}


@dataclass
class Measurement:
    """What a metric function returns."""
    value: Optional[float]
    numerator: Optional[float] = None
    denominator: Optional[float] = None
    n: int = 0
    breakdown: Optional[Any] = None


@dataclass
class MetricSpec:
    id: str
    name: str
    category: str
    unit: str  # "rate" | "ms" | "s" | "count" | "usd" | "tokens"
    good: Optional[str]  # "up" | "down" | None (informational)
    target: Optional[float]
    description: str
    fn: Callable[[MetricContext], Measurement]
    min_n: int = 10
    sparkline: bool = True


REGISTRY: Dict[str, MetricSpec] = {}


def metric(id: str, name: str, category: str, unit: str, description: str,
           good: Optional[str] = None, target: Optional[float] = None,
           min_n: int = 10, sparkline: bool = True):
    if category not in dict(CATEGORIES):
        raise ValueError(f"Unknown metric category {category!r}.")

    def register(fn: Callable[[MetricContext], Measurement]):
        if id in REGISTRY:
            raise ValueError(f"Metric {id!r} is already registered.")
        REGISTRY[id] = MetricSpec(id, name, category, unit, good, target, description, fn, min_n, sparkline)
        return fn
    return register


def status_for(spec: MetricSpec, value: Optional[float], n: int) -> str:
    if value is None:
        return "no_data"
    if n < spec.min_n:
        return "low_sample"
    if spec.target is None or spec.good is None:
        return "info"
    if spec.good == "up":
        return "good" if value >= spec.target else "warn" if value >= spec.target * 0.9 else "bad"
    return "good" if value <= spec.target else "warn" if value <= spec.target * 1.2 else "bad"


def _measure(spec: MetricSpec, ctx: MetricContext) -> Measurement:
    try:
        return spec.fn(ctx)
    except Exception:  # one broken metric must not take the whole scorecard down
        return Measurement(None, breakdown={"error": "metric failed to compute"})


def evaluate_metric(spec: MetricSpec, current: MetricContext, previous: Optional[MetricContext] = None,
                    full_series: bool = False) -> Dict[str, Any]:
    measured = _measure(spec, current)
    before = _measure(spec, previous) if previous is not None else None
    delta = (
        measured.value - before.value
        if measured.value is not None and before is not None and before.value is not None else None
    )
    result: Dict[str, Any] = {
        "id": spec.id, "name": spec.name, "category": spec.category, "unit": spec.unit,
        "good": spec.good, "target": spec.target, "description": spec.description,
        "value": measured.value, "numerator": measured.numerator, "denominator": measured.denominator,
        "n": measured.n, "status": status_for(spec, measured.value, measured.n),
        "previous": before.value if before else None, "delta": delta,
        "breakdown": measured.breakdown,
    }
    if spec.sparkline:
        days = current.by_day()
        keys = sorted(days)
        if not full_series:
            keys = keys[-SPARKLINE_DAYS:]
        result["series"] = [{"date": day, "value": _measure(spec, days[day]).value} for day in keys]
    return result


def scorecard(rows: List[Dict[str, Any]], days: int, now: Optional[datetime] = None,
              only: Optional[str] = None, truncated: bool = False) -> Dict[str, Any]:
    """Evaluate every registered metric over the last `days`, compared with the previous `days`."""
    now = now or datetime.now(timezone.utc)
    events = to_events(rows)
    cutoff = now - timedelta(days=days)
    previous_cutoff = now - timedelta(days=days * 2)
    current = MetricContext([e for e in events if e.at >= cutoff], now)
    previous = MetricContext([e for e in events if previous_cutoff <= e.at < cutoff], now)

    specs = [REGISTRY[only]] if only else list(REGISTRY.values())
    results = [evaluate_metric(spec, current, previous, full_series=bool(only)) for spec in specs]
    return {
        "generated_at": now.isoformat(),
        "window_days": days,
        "events_in_window": len(current.events),
        "data_truncated": truncated,
        "categories": [
            {"id": cid, "name": cname, "metrics": [r for r in results if r["category"] == cid]}
            for cid, cname in CATEGORIES
            if any(r["category"] == cid for r in results)
        ],
    }
