"""Test error classification with real provider error payloads."""

import pytest
from unittest.mock import MagicMock
from app.synthesis.errors import classify_provider_error, ErrorClassification


def test_gemini_503_unavailable():
    """Real Gemini 503 from user logs."""
    error = MagicMock()
    error.status_code = 503
    error.__str__ = lambda self: (
        "503 UNAVAILABLE. {'error': {'code': 503, 'message': "
        "'This model is currently experiencing high demand. Spikes in demand "
        "are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}"
    )

    classification = classify_provider_error(error, "gemini")

    assert classification.provider == "gemini"
    assert classification.kind == "unavailable"
    assert classification.retryable is True
    assert classification.http_status == 503
    assert classification.retry_after_seconds is not None


def test_gemini_429_daily_quota():
    """Real Gemini 429 daily quota from user logs."""
    error = MagicMock()
    error.status_code = 429
    error.__str__ = lambda self: (
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': "
        "'You exceeded your current quota, please check your plan and billing details. "
        "Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, "
        "limit: 20, model: gemini-3.6-flash', 'status': 'RESOURCE_EXHAUSTED', "
        "'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', "
        "'retryDelay': '61934s'}]}}"
    )

    classification = classify_provider_error(error, "gemini")

    assert classification.provider == "gemini"
    assert classification.kind == "quota_daily"
    assert classification.retryable is True
    assert classification.http_status == 429
    assert classification.retry_after_seconds == 61934
    assert "hours" in classification.public_message.lower()


def test_anthropic_429_rate_limit():
    """Claude rate limit (short-term)."""
    error = MagicMock()
    error.status_code = 429
    error.__str__ = lambda self: "429 Rate limit exceeded"

    classification = classify_provider_error(error, "anthropic")

    assert classification.provider == "anthropic"
    assert classification.kind == "rate_limited"
    assert classification.retryable is True
    assert classification.http_status == 429
    assert classification.retry_after_seconds >= 60


def test_anthropic_401_auth_error():
    """Invalid API key."""
    error = MagicMock()
    error.status_code = 401
    error.__str__ = lambda self: "401 Unauthorized"

    classification = classify_provider_error(error, "anthropic")

    assert classification.provider == "anthropic"
    assert classification.kind == "auth"
    assert classification.retryable is False
    assert classification.http_status == 401


def test_anthropic_400_bad_request():
    """Invalid request format."""
    error = MagicMock()
    error.status_code = 400
    error.__str__ = lambda self: "400 Bad Request"

    classification = classify_provider_error(error, "anthropic")

    assert classification.provider == "anthropic"
    assert classification.kind == "bad_request"
    assert classification.retryable is False
    assert classification.http_status == 400


def test_unknown_error():
    """Unclassified error defaults to retryable unknown."""
    error = MagicMock()
    error.status_code = None
    error.__str__ = lambda self: "Some unrecognized error"

    classification = classify_provider_error(error, "unknown_provider")

    assert classification.kind == "unknown"
    assert classification.retryable is True
    assert classification.http_status is None
