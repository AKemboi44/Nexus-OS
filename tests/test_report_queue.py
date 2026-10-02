import asyncio
import time
import pytest
from types import SimpleNamespace
from pathlib import Path

from app.reports.queue_config import ReportQueueConfig
from app.reports.report_queue import ReportQueueManager, QueuedReportJob
from app.notifications.notification_service import NotificationService
from app.synthesis.providers import (
    SynthesisProvider,
    SynthesisProviderRegistry,
    SynthesisRateLimitError,
    SynthesisUnavailableError,
    SynthesisProviderError,
    DegradationLogger,
)
import cloud_app


class MockFailingProvider(SynthesisProvider):
    name = "mock_failing"

    def is_configured(self) -> bool:
        return True

    def generate_text(self, prompt: str, **kwargs) -> str:
        err = SynthesisRateLimitError("429 Quota Exceeded", provider=self.name)
        DegradationLogger.log_degradation(self.name, err.error_type, str(err))
        raise err


class MockWorkingProvider(SynthesisProvider):
    name = "mock_working"

    def is_configured(self) -> bool:
        return True

    def generate_text(self, prompt: str, **kwargs) -> str:
        return "ABSTRACT: Valid synthesis\nKEY THEMES: Theme 1\nCONTRADICTIONS: Contradiction 1\nRESEARCH GAPS: Gap 1\nRESEARCH AREAS: Area 1\nOPPORTUNITY AREAS: Opportunity 1\nPROBLEMS TO SOLVE: Problem 1\n"


def test_provider_failover_and_degradation_logging():
    DegradationLogger.clear_events()
    failing = MockFailingProvider()
    working = MockWorkingProvider()
    registry = SynthesisProviderRegistry(providers=[failing, working])

    text, provider = registry.generate_with_failover("Test prompt")
    assert provider == "mock_working"
    assert "Valid synthesis" in text

    events = DegradationLogger.get_events()
    assert len(events) >= 1
    assert events[0]["provider"] == "mock_failing"
    assert events[0]["error_type"] == "rate_limit_or_quota"
    assert "timestamp" in events[0]


def test_queue_config_defaults_and_override():
    config = ReportQueueConfig()
    assert config.estimated_wait_range == "usually under 20 minutes"
    assert config.max_retries == 3
    assert config.timeout_window_seconds == 1200.0

    custom = ReportQueueConfig(
        estimated_wait_range="5-10 minutes",
        max_retries=5,
        timeout_window_seconds=600.0,
    )
    assert custom.estimated_wait_range == "5-10 minutes"
    assert custom.max_retries == 5
    assert custom.timeout_window_seconds == 600.0


def test_queue_enqueue_and_status_tracking():
    NotificationService.clear_all()
    queue = ReportQueueManager(config=ReportQueueConfig())
    job = queue.enqueue(
        user_id="user-123",
        topic="AI Ethics",
        report_type="proposal",
        domain="scholarly",
        included_sources=[{"title": "Paper 1"}],
        initial_error="Rate limit error",
        user_email="user@test.com",
    )

    assert job.status == "queued"
    assert job.topic == "AI Ethics"
    assert job.estimated_wait == "usually under 20 minutes"
    assert job.created_at is not None
    assert job.attempts == 1

    # Status check
    retrieved = queue.get_job(job.id)
    assert retrieved is not None
    assert retrieved.status == "queued"


def test_exponential_backoff_and_permanent_failure_with_notification():
    NotificationService.clear_all()
    config = ReportQueueConfig(
        max_retries=2,
        initial_backoff_seconds=0.01,
        backoff_multiplier=2.0,
        timeout_window_seconds=100.0,
    )
    queue = ReportQueueManager(config=config)
    job = queue.enqueue(
        user_id="user-456",
        topic="Quantum Computing",
        report_type="proposal",
        user_email="quantum@test.com",
        immediate_retry=True,
    )

    # First attempt fails -> queued with backoff
    queue.process_pending_jobs()
    job = queue.get_job(job.id)
    assert job.attempts >= 1

    # Wait for backoff
    time.sleep(0.05)
    # Second attempt exceeds max_retries (2) -> failed
    queue.process_pending_jobs()
    job = queue.get_job(job.id)
    assert job.status == "failed"
    assert job.error_reason is not None

    # Verify notifications
    notifications = NotificationService.get_user_notifications("user-456")
    assert len(notifications) == 1
    assert notifications[0]["event"] == "report_failed"
    assert notifications[0]["retry_action"] is not None
    assert notifications[0]["retry_action"]["endpoint"] == f"/api/reports/{job.id}/retry"

    emails = NotificationService.get_sent_emails("user-456")
    assert len(emails) == 1
    assert emails[0]["event"] == "report_failed"
    assert emails[0]["to_email"] == "quantum@test.com"


def test_timeout_window_marks_report_failed():
    NotificationService.clear_all()
    config = ReportQueueConfig(
        max_retries=5,
        timeout_window_seconds=0.05,  # short timeout
    )
    queue = ReportQueueManager(config=config)
    job = queue.enqueue(
        user_id="user-789",
        topic="Neural Networks",
        user_email="nn@test.com",
    )
    time.sleep(0.06)
    queue.process_pending_jobs()

    job = queue.get_job(job.id)
    assert job.status == "failed"
    assert "timed out" in job.error_reason.lower()


def test_manual_retry_job_re_enqueues():
    queue = ReportQueueManager()
    job = queue.enqueue(user_id="user-1", topic="Topic")
    queue.mark_failed(job.id, "Some failure")
    assert queue.get_job(job.id).status == "failed"

    queue.retry_job(job.id)
    assert queue.get_job(job.id).status == "queued"
    assert queue.get_job(job.id).attempts == 0


def test_job_to_dict_standard_status_and_download_url():
    queue = ReportQueueManager()
    job = queue.enqueue(user_id="user-xyz", topic="Async Architecture")
    d = job.to_dict()
    assert d["status"] == "queued"
    assert d["is_completed"] is False
    assert d["download_url"] is None

    # Mark ready / completed
    queue.mark_ready(job.id, b"fake_docx_bytes", "async-report.docx")
    d_ready = job.to_dict()
    assert d_ready["status"] == "completed"
    assert d_ready["is_completed"] is True
    assert d_ready["download_url"] == f"/v1/reports/{job.id}/download"
    assert d_ready["document_name"] == "async-report.docx"
