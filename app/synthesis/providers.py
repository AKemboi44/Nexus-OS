from __future__ import annotations

import os
import sys
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

logger = logging.getLogger("nexus.synthesis.providers")


class SynthesisProviderError(RuntimeError):
    """Base exception for synthesis provider errors."""
    def __init__(self, message: str, provider: str = "unknown", error_type: str = "general_error", raw_error: Optional[Exception] = None):
        super().__init__(message)
        self.provider = provider
        self.error_type = error_type
        self.raw_error = raw_error
        self.timestamp = datetime.now(timezone.utc).isoformat()


class SynthesisRateLimitError(SynthesisProviderError):
    """Raised when an AI synthesis provider hits quota or rate limits."""
    def __init__(self, message: str, provider: str = "unknown", raw_error: Optional[Exception] = None):
        super().__init__(message, provider=provider, error_type="rate_limit_or_quota", raw_error=raw_error)


class SynthesisUnavailableError(SynthesisProviderError):
    """Raised when an AI synthesis provider is unavailable or unconfigured."""
    def __init__(self, message: str, provider: str = "unknown", raw_error: Optional[Exception] = None):
        super().__init__(message, provider=provider, error_type="service_unavailable", raw_error=raw_error)


# Degradation Event Logger
class DegradationLogger:
    _events: List[Dict[str, Any]] = []

    @classmethod
    def log_degradation(cls, provider: str, error_type: str, details: Optional[str] = None, timestamp: Optional[str] = None) -> Dict[str, Any]:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        event = {
            "provider": provider,
            "error_type": error_type,
            "timestamp": ts,
            "details": str(details) if details else None,
        }
        cls._events.append(event)
        logger.warning(
            "[Synthesis Degradation Event] provider=%s error_type=%s timestamp=%s details=%s",
            provider, error_type, ts, details
        )
        return event

    @classmethod
    def get_events(cls) -> List[Dict[str, Any]]:
        return list(cls._events)

    @classmethod
    def clear_events(cls) -> None:
        cls._events.clear()


# Errors worth one more try on the same provider: short-lived overload, timeouts and connection trouble.
# Quota and "exhausted" errors are not: they will not clear in a second.
_TRANSIENT_MARKERS = (
    "503", "529", "502", "504", "429", "overloaded", "unavailable", "high demand", "timeout", "timed out",
    "connection", "rate_limit", "rate limit",
)
_NOT_TRANSIENT_MARKERS = ("quota", "exhausted", "billing", "api key", "invalid_api_key", "permission", "not found")


def is_transient_error(error: Exception) -> bool:
    # The provider wrappers prefix their own wording ("quota/rate limit: ..."); judge the original error.
    message = str(getattr(error, "raw_error", None) or error).lower()
    if any(marker in message for marker in _NOT_TRANSIENT_MARKERS):
        return False
    return any(marker in message for marker in _TRANSIENT_MARKERS)


class SynthesisProvider(ABC):
    """Unified interface for AI synthesis providers."""
    name: str = "base"
    provider: str = "unknown"
    # (input tokens, output tokens) of the most recent generate_text call, for cost tracking.
    last_usage: Optional[Tuple[Optional[int], Optional[int]]] = None

    @abstractmethod
    def generate_text(self, prompt: str, **kwargs) -> str:
        """Generate text given a prompt."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider credentials/client are configured."""
        pass

    async def generate_structured_once(
        self,
        prompt_user: str,
        prompt_system: str,
        schema: dict,
        model: str = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> dict:
        """Generate structured JSON matching a schema, no retries."""
        raise NotImplementedError(f"{self.name} does not support structured generation")


class GeminiSynthesisProvider(SynthesisProvider):
    name = "gemini"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning("Could not initialize Gemini client: %s", e)

    def is_configured(self) -> bool:
        return self.client is not None

    def generate_text(self, prompt: str, **kwargs) -> str:
        if not self.is_configured():
            err = SynthesisUnavailableError("Gemini provider is not configured", provider=self.name)
            DegradationLogger.log_degradation(self.name, err.error_type, str(err))
            raise err
        model_name = kwargs.get("model", self.model)
        try:
            self.last_usage = None
            if hasattr(self.client, "models") and hasattr(self.client.models, "generate_content"):
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
            elif hasattr(self.client, "generate_content"):
                response = self.client.generate_content(prompt)
            elif hasattr(self.client, "GenerativeModel"):
                gen_model = self.client.GenerativeModel(model_name)
                response = gen_model.generate_content(prompt)
            else:
                raise AttributeError(f"Unsupported Gemini client structure: {type(self.client)}")
            meta = getattr(response, "usage_metadata", None)
            self.last_usage = (getattr(meta, "prompt_token_count", None), getattr(meta, "candidates_token_count", None))
            return getattr(response, "text", "") or ""
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str or "rate" in err_str:
                err = SynthesisRateLimitError(f"Gemini quota/rate limit: {e}", provider=self.name, raw_error=e)
            else:
                err = SynthesisProviderError(f"Gemini generation error: {e}", provider=self.name, error_type="provider_error", raw_error=e)
            DegradationLogger.log_degradation(self.name, err.error_type, str(e))
            raise err

    async def generate_structured_once(
        self,
        prompt_user: str,
        prompt_system: str,
        schema: dict,
        model: str = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> dict:
        """Generate JSON matching schema via Gemini."""
        if not self.is_configured():
            raise SynthesisUnavailableError("Gemini provider is not configured", provider=self.name)

        model_name = model or self.model
        try:
            # Request JSON as plain text (more reliable than response_mime_type)
            response = self.client.models.generate_content(
                model=model_name,
                contents=f"{prompt_system}\n\nRespond with ONLY a valid JSON object, starting with {{ and ending with }}, no markdown, no extra text:\n\n{prompt_user}",
                config={
                    "max_output_tokens": max_tokens,
                }
            )

            content = getattr(response, "text", "") or ""
            logger.info("Gemini raw response length: %d chars", len(content))

            if not content or content.strip() == "":
                logger.error("Gemini returned empty response")
                raise SynthesisProviderError(
                    "Gemini returned empty response",
                    provider=self.name,
                    error_type="empty_response"
                )

            return {
                "content": content.strip(),
                "provider": self.name,
                "model": model_name,
                "input_tokens": getattr(response.usage, "prompt_token_count", None),
                "output_tokens": getattr(response.usage, "candidates_token_count", None),
            }
        except Exception as e:
            DegradationLogger.log_degradation(self.name, "provider_error", str(e))
            raise


class ClaudeSynthesisProvider(SynthesisProvider):
    name = "anthropic"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, timeout: float = 180.0):
        self.api_key = api_key or os.getenv("CLAUDE_API_KEY")
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
        self.timeout = timeout
        self.client = None
        if self.api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(
                    api_key=self.api_key,
                    timeout=self.timeout,
                    max_retries=0,
                )
            except Exception as e:
                logger.warning("Could not initialize Anthropic client: %s", e)

    def is_configured(self) -> bool:
        return self.client is not None

    def generate_text(self, prompt: str, **kwargs) -> str:
        if not self.is_configured():
            err = SynthesisUnavailableError("Anthropic provider is not configured", provider=self.name)
            DegradationLogger.log_degradation(self.name, err.error_type, str(err))
            raise err
        model_name = kwargs.get("model", self.model)
        try:
            self.last_usage = None
            response = self.client.messages.create(
                model=model_name,
                max_tokens=kwargs.get("max_tokens", 4096),
                messages=[{"role": "user", "content": prompt}],
            )
            usage = getattr(response, "usage", None)
            self.last_usage = (getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None))
            text_blocks = [block.text for block in response.content if getattr(block, "type", "") == "text"]
            return "".join(text_blocks)
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate_limit" in err_str or "quota" in err_str or "overloaded" in err_str:
                err = SynthesisRateLimitError(f"Anthropic quota/rate limit: {e}", provider=self.name, raw_error=e)
            else:
                err = SynthesisProviderError(f"Anthropic generation error: {e}", provider=self.name, error_type="provider_error", raw_error=e)
            DegradationLogger.log_degradation(self.name, err.error_type, str(e))
            raise err

    async def generate_structured_once(
        self,
        prompt_user: str,
        prompt_system: str,
        schema: dict,
        model: str = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> dict:
        """Generate JSON matching schema via Claude."""
        if not self.is_configured():
            raise SynthesisUnavailableError("Anthropic provider is not configured", provider=self.name)

        model_name = model or self.model
        try:
            response = self.client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                system=prompt_system,
                messages=[{"role": "user", "content": prompt_user}],
            )
            content = "".join(
                block.text for block in response.content
                if getattr(block, "type", None) == "text"
            )
            return {
                "content": content,
                "provider": self.name,
                "model": model_name,
                "input_tokens": response.usage.input_tokens if hasattr(response, "usage") else None,
                "output_tokens": response.usage.output_tokens if hasattr(response, "usage") else None,
            }
        except Exception as e:
            DegradationLogger.log_degradation(self.name, "provider_error", str(e))
            raise


class SynthesisProviderRegistry:
    """Registry and manager for synthesis providers with failover support."""
    def __init__(self, providers: Optional[List[Any]] = None):
        self._providers: List[SynthesisProvider] = providers if providers is not None else self._discover_providers()

    @classmethod
    def _discover_providers(cls) -> List[SynthesisProvider]:
        provs = []
        claude = ClaudeSynthesisProvider()
        if claude.is_configured():
            provs.append(claude)
        gemini = GeminiSynthesisProvider()
        if gemini.is_configured():
            provs.append(gemini)
        if not provs:
            # Provide default instances even if keys not yet loaded (e.g. for testing / late loading)
            provs = [ClaudeSynthesisProvider(), GeminiSynthesisProvider()]
        return provs

    def get_primary_provider(self) -> SynthesisProvider:
        for p in self._providers:
            if p.is_configured():
                return p
        return self._providers[0] if self._providers else GeminiSynthesisProvider()

    retry_delay_seconds = float(os.getenv("SYNTHESIS_RETRY_DELAY_SECONDS", "1.5"))

    @staticmethod
    def _begin(ledger, purpose, provider, attempt):
        if ledger is None:
            return None
        try:
            call = ledger.add_call(purpose, provider.name, str(getattr(provider, "model", "unknown")), attempt)
        except RuntimeError:
            return None  # the call budget is a safety net; it must never break a scan
        return call, time.monotonic()

    @staticmethod
    def _end(ledger, handle, provider, outcome, error=None):
        if handle is None:
            return
        call, started = handle
        usage = getattr(provider, "last_usage", None) if outcome == "ok" else None
        input_tokens, output_tokens = usage if usage else (None, None)
        ledger.complete_call(
            call, outcome,
            input_tokens=input_tokens if isinstance(input_tokens, int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
            latency_ms=int((time.monotonic() - started) * 1000),
            error_kind=getattr(error, "error_type", None) if error is not None else None,
        )

    def generate_with_failover(self, prompt: str, **kwargs) -> tuple[str, str]:
        """Attempts generation with available providers in order.

        A transient error (overload, timeout) is retried once on the same provider before moving on, and
        every attempt is recorded in `ledger` (with `purpose`) when one is given.
        Returns tuple of (generated_text, provider_name).
        Raises SynthesisProviderError if all providers fail.
        """
        ledger = kwargs.pop("ledger", None)
        purpose = kwargs.pop("purpose", "synthesis")
        last_error = None
        for provider in self._providers:
            if not provider.is_configured():
                continue
            for attempt in (1, 2):
                handle = self._begin(ledger, purpose, provider, attempt)
                try:
                    text = provider.generate_text(prompt, **kwargs)
                except SynthesisProviderError as e:
                    self._end(ledger, handle, provider, "provider_error", error=e)
                    last_error = e
                    if attempt == 1 and is_transient_error(e):
                        logger.info("Provider %s hit a transient error; retrying once.", provider.name)
                        time.sleep(self.retry_delay_seconds)
                        continue
                    logger.info("Provider %s failed, trying next provider if available...", provider.name)
                    break
                self._end(ledger, handle, provider, "ok")
                return text, provider.name
        if last_error:
            raise last_error
        err = SynthesisUnavailableError("No synthesis provider configured or available")
        DegradationLogger.log_degradation("none", err.error_type, str(err))
        raise err
