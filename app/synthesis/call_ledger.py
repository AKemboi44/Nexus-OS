"""Per-request record of model calls: outcome, latency and tokens. Passed explicitly, never global."""

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

OK = "ok"
PROVIDER_ERROR = "provider_error"
INVALID_OUTPUT = "invalid_output"
QUALITY_GATE = "quality_gate"


@dataclass
class LLMCall:
    """A single model provider call."""
    purpose: str
    provider: str
    model: str
    attempt: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    outcome: str = "pending"
    http_status: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    error_kind: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RequestLedger:
    """All model calls made while serving one request."""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    calls: List[LLMCall] = field(default_factory=list)
    max_calls: int = 4

    def add_call(self, purpose: str, provider: str, model: str, attempt: int = 1) -> LLMCall:
        if len(self.calls) >= self.max_calls:
            raise RuntimeError(
                f"LLM call budget exceeded ({self.max_calls}). Purpose: {purpose}, Provider: {provider}"
            )
        call = LLMCall(purpose=purpose, provider=provider, model=model, attempt=attempt)
        self.calls.append(call)
        return call

    def complete_call(
        self,
        call: LLMCall,
        outcome: str,
        http_status: Optional[int] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        latency_ms: Optional[int] = None,
        error_kind: Optional[str] = None,
    ) -> None:
        call.outcome = outcome
        call.http_status = http_status
        call.input_tokens = input_tokens
        call.output_tokens = output_tokens
        call.latency_ms = latency_ms
        call.error_kind = error_kind

    def summary(self) -> Dict:
        total_input = sum(call.input_tokens or 0 for call in self.calls)
        total_output = sum(call.output_tokens or 0 for call in self.calls)
        return {
            "request_id": self.request_id,
            "call_count": len(self.calls),
            "total_input_tokens": total_input or None,
            "total_output_tokens": total_output or None,
            "calls": [call.to_dict() for call in self.calls],
        }

    def log_summary(self) -> None:
        logger.info("[LLM Call Ledger] %s", json.dumps(self.summary()))
