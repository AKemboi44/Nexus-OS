"""Error classification for provider failures with retry guidance."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ErrorClassification:
    """Typed error information for provider failures."""
    provider: str
    kind: str
    retryable: bool
    retry_after_seconds: Optional[int] = None
    http_status: Optional[int] = None
    public_message: Optional[str] = None


def classify_provider_error(error: Exception, provider: str) -> ErrorClassification:
    """
    Classify a provider error into a typed, actionable category.

    Args:
        error: The exception from Claude or Gemini
        provider: "anthropic" or "gemini"

    Returns:
        ErrorClassification with kind, retryability, and honest retry delay
    """
    error_str = str(error).lower()
    http_status = _http_status(error)

    if http_status == 401:
        return ErrorClassification(
            provider=provider,
            kind="auth",
            retryable=False,
            http_status=401,
            public_message=f"{provider.title()} rejected the API key. Check credentials.",
        )

    if http_status == 403:
        return ErrorClassification(
            provider=provider,
            kind="auth",
            retryable=False,
            http_status=403,
            public_message=f"{provider.title()} denied access. Check model access and permissions.",
        )

    if http_status == 404:
        return ErrorClassification(
            provider=provider,
            kind="config",
            retryable=False,
            http_status=404,
            public_message=f"Configured model not found in {provider.title()}. Check model name.",
        )

    if http_status == 400:
        return ErrorClassification(
            provider=provider,
            kind="bad_request",
            retryable=False,
            http_status=400,
            public_message=f"{provider.title()} rejected the request. Check the request format.",
        )

    if http_status == 429:
        retry_after = _parse_retry_after(error, provider)
        if provider == "gemini" and retry_after and retry_after > 3600:
            return ErrorClassification(
                provider=provider,
                kind="quota_daily",
                retryable=True,
                http_status=429,
                retry_after_seconds=retry_after,
                public_message=f"Daily quota exhausted. Retry in {_format_retry_delay(retry_after)}.",
            )
        return ErrorClassification(
            provider=provider,
            kind="rate_limited",
            retryable=True,
            http_status=429,
            retry_after_seconds=retry_after or 60,
            public_message=f"{provider.title()} rate limit reached. Retrying shortly.",
        )

    if http_status and http_status >= 500:
        retry_after = _parse_retry_after(error, provider)
        if http_status == 503:
            return ErrorClassification(
                provider=provider,
                kind="unavailable",
                retryable=True,
                http_status=503,
                retry_after_seconds=retry_after or 30,
                public_message=f"{provider.title()} is temporarily overloaded. Will retry.",
            )
        return ErrorClassification(
            provider=provider,
            kind="unavailable",
            retryable=True,
            http_status=http_status,
            retry_after_seconds=retry_after or 60,
            public_message=f"{provider.title()} service error. Will retry.",
        )

    if "output_truncated" in error_str or "max_tokens" in error_str:
        return ErrorClassification(
            provider=provider,
            kind="output_truncated",
            retryable=True,
            http_status=http_status,
            public_message="Output was truncated. Retrying with adjusted settings.",
        )

    return ErrorClassification(
        provider=provider,
        kind="unknown",
        retryable=True,
        http_status=http_status,
        public_message=f"{provider.title()} request failed. Will retry.",
    )


def _http_status(error: Exception) -> Optional[int]:
    """Extract HTTP status from error."""
    if hasattr(error, "status_code"):
        return error.status_code
    response = getattr(error, "response", None)
    if response and hasattr(response, "status_code"):
        return response.status_code
    return None


def _parse_retry_after(error: Exception, provider: str) -> Optional[int]:
    """
    Extract retry-after delay from error, honoring provider conventions.

    Google Gemini uses RetryInfo.retryDelay in the error details.
    Anthropic and HTTP use Retry-After header or don't provide it.
    """
    if provider == "gemini":
        error_str = str(error)
        match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s", error_str)
        if match:
            return int(match.group(1))

    response = getattr(error, "response", None)
    if response:
        if hasattr(response, "headers"):
            if "retry-after" in response.headers:
                try:
                    return int(response.headers["retry-after"])
                except (ValueError, TypeError):
                    pass

    return None


def _format_retry_delay(seconds: int) -> str:
    """Format seconds into human-readable delay."""
    if seconds < 60:
        return f"{seconds} seconds"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    hours = seconds // 3600
    return f"{hours} hour{'s' if hours > 1 else ''}"
