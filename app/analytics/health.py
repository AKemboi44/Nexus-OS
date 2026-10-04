"""Instrumentation health: is every expected event arriving, from the right place, and well-formed?"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.analytics import schema
from app.analytics.metrics_engine import to_events


def instrumentation_health(rows: List[Dict[str, Any]], days: int, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    per_event: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "last_seen": None, "sources": Counter(), "schema_problems": 0}
    )
    for event in to_events(rows):
        entry = per_event[event.name]
        entry["count"] += 1
        entry["sources"][event.source] += 1
        if event.props.get("_schema_problems") or event.props.get("_unregistered"):
            entry["schema_problems"] += 1
        if entry["last_seen"] is None or event.at > entry["last_seen"]:
            entry["last_seen"] = event.at

    events = [
        {
            "event": name,
            "registered": schema.get(name) is not None,
            "count": entry["count"],
            "last_seen": entry["last_seen"].isoformat(),
            "sources": dict(entry["sources"]),
            "schema_problems": entry["schema_problems"],
        }
        for name, entry in sorted(per_event.items(), key=lambda item: -item[1]["count"])
    ]
    never_seen = [
        {"event": spec.name, "expected_from": list(spec.sources), "stage": spec.stage}
        for spec in schema.REGISTRY.values() if spec.name not in per_event
    ]
    return {
        "generated_at": now.isoformat(),
        "window_days": days,
        "events": events,
        "never_seen": never_seen,
        "unregistered": [e["event"] for e in events if not e["registered"]],
    }
