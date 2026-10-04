"""Per-request correlation id, app version and log configuration."""

import logging
import os
import re
import uuid
from contextvars import ContextVar
from typing import Optional

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_QUIET_LOGGERS = ("httpx", "httpcore", "urllib3")
_logging_configured = False


def new_request_id() -> str:
    return str(uuid.uuid4())


def accept_request_id(candidate: Optional[str]) -> str:
    """Reuse a well-formed inbound X-Request-ID, otherwise mint a new one."""
    if candidate and _VALID_REQUEST_ID.match(candidate):
        return candidate
    return new_request_id()


def set_request_id(value: Optional[str]):
    return _request_id.set(value)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def current_request_id() -> Optional[str]:
    return _request_id.get()


def app_version() -> Optional[str]:
    sha = os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("APP_VERSION")
    return sha[:12] if sha else None


def configure_logging() -> None:
    """Make INFO logs visible and stamp every record with the current request id."""
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True
    previous_factory = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = previous_factory(*args, **kwargs)
        record.request_id = current_request_id() or "-"
        return record

    logging.setLogRecordFactory(factory)
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s",
    )
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
