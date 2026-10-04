"""Lightweight spans: timed sections of a request, recorded as `span` analytics events."""

import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

Sink = Callable[[str, str, Dict[str, Any]], None]
_sink: Optional[Sink] = None


def set_sink(sink: Optional[Sink]) -> None:
    """Install the function that persists events: (event_name, user_id, properties)."""
    global _sink
    _sink = sink


def record_span(user_id: str, name: str, duration_ms: float, outcome: str = "ok", **attrs: Any) -> None:
    if _sink is None:
        return
    try:
        _sink("span", user_id, {"name": name, "duration_ms": max(0, int(duration_ms)), "outcome": outcome, **attrs})
    except Exception:
        logger.exception("Could not record span %s.", name)


@contextmanager
def traced(user_id: str, name: str, **attrs: Any):
    started = time.monotonic()
    outcome = "ok"
    try:
        yield
    except Exception:
        outcome = "error"
        raise
    finally:
        record_span(user_id, name, (time.monotonic() - started) * 1000, outcome, **attrs)
