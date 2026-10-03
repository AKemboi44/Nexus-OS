"""Per-request LLM call tracking for cost and debugging visibility."""

import json
import logging
import uuid
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Per-request context: tracks all LLM calls for a single report/proposal request
_request_ledger: ContextVar[Optional["RequestLedger"]] = ContextVar(
    "request_ledger", default=None
)


@dataclass
class LLMCall:
    """A single LLM provider call."""
    purpose: str
    provider: str
    model: str
    attempt: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    outcome: str = "pending"
    http_status: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error_message: Optional[str] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class RequestLedger:
    """Tracks all LLM calls in a single request lifecycle."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    calls: list[LLMCall] = field(default_factory=list)
    max_calls: int = 4

    def add_call(
        self,
        purpose: str,
        provider: str,
        model: str,
        attempt: int = 1,
    ) -> LLMCall:
        """Record a new LLM call."""
        if len(self.calls) >= self.max_calls:
            raise RuntimeError(
                f"LLM call budget exceeded ({self.max_calls}). "
                f"Purpose: {purpose}, Provider: {provider}"
            )
        call = LLMCall(
            purpose=purpose,
            provider=provider,
            model=model,
            attempt=attempt,
        )
        self.calls.append(call)
        return call

    def complete_call(
        self,
        call: LLMCall,
        outcome: str,
        http_status: Optional[int] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        """Mark a call complete."""
        call.outcome = outcome
        call.http_status = http_status
        call.input_tokens = input_tokens
        call.output_tokens = output_tokens
        call.error_message = error_message

    def summary(self) -> dict:
        """Summary of all calls for logging."""
        total_input = sum(c.input_tokens or 0 for c in self.calls)
        total_output = sum(c.output_tokens or 0 for c in self.calls)
        return {
            "request_id": self.request_id,
            "call_count": len(self.calls),
            "max_calls": self.max_calls,
            "total_input_tokens": total_input if total_input > 0 else None,
            "total_output_tokens": total_output if total_output > 0 else None,
            "by_provider": {
                provider: {
                    "count": sum(1 for c in self.calls if c.provider == provider),
                    "outcomes": list(
                        set(c.outcome for c in self.calls if c.provider == provider)
                    ),
                }
                for provider in set(c.provider for c in self.calls)
            },
            "calls": [c.to_dict() for c in self.calls],
        }

    def log_summary(self):
        """Emit a structured log with all call details."""
        summary = self.summary()
        logger.info(
            "[LLM Call Ledger] %s",
            json.dumps(summary),
            extra={"request_id": self.request_id},
        )


def get_request_ledger() -> Optional[RequestLedger]:
    """Get the current request's ledger."""
    return _request_ledger.get()


def set_request_ledger(ledger: Optional[RequestLedger]):
    """Set the request ledger (e.g., at the start of /v1/reports)."""
    _request_ledger.set(ledger)


def start_request_ledger(max_calls: int = 4) -> RequestLedger:
    """Start a new request ledger and set it in context."""
    ledger = RequestLedger(max_calls=max_calls)
    set_request_ledger(ledger)
    return ledger
