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


class SynthesisProvider(ABC):
    """Unified interface for AI synthesis providers."""
    name: str = "base"
    provider: str = "unknown"

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
            # Build JSON mode request
            response = self.client.models.generate_content(
                model=model_name,
                contents=f"{prompt_system}\n\n{prompt_user}",
                config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                    "response_mime_type": "application/json",
                }
            )
            content = getattr(response, "text", "") or ""
            return {
                "content": content,
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
            response = self.client.messages.create(
                model=model_name,
                max_tokens=kwargs.get("max_tokens", 4096),
                messages=[{"role": "user", "content": prompt}],
            )
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
                temperature=temperature,
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

    def generate_with_failover(self, prompt: str, **kwargs) -> tuple[str, str]:
        """Attempts generation with available providers in order.
        Returns tuple of (generated_text, provider_name).
        Raises SynthesisProviderError if all providers fail.
        """
        last_error = None
        for provider in self._providers:
            if not provider.is_configured():
                continue
            try:
                text = provider.generate_text(prompt, **kwargs)
                return text, provider.name
            except SynthesisProviderError as e:
                last_error = e
                logger.info("Provider %s failed, trying next provider if available...", provider.name)
                continue
        if last_error:
            raise last_error
        err = SynthesisUnavailableError("No synthesis provider configured or available")
        DegradationLogger.log_degradation("none", err.error_type, str(err))
        raise err
