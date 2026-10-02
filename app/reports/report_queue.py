import os
import sys
import time
import math
import base64
import tempfile
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from uuid import uuid4

from app.reports.queue_config import ReportQueueConfig, default_queue_config
from app.notifications.notification_service import NotificationService
from app.synthesis.providers import DegradationLogger, SynthesisProviderError

logger = logging.getLogger("nexus.report_queue")


class QueuedReportJob:
    def __init__(
        self,
        job_id: str,
        user_id: str,
        topic: str,
        report_type: str = "proposal",
        domain: str = "scholarly",
        custom_prompt: Optional[str] = None,
        included_sources: Optional[list] = None,
        status: str = "queued",  # queued, generating, ready, failed
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        attempts: int = 0,
        next_retry_at: float = 0.0,
        error_reason: Optional[str] = None,
        document_base64: Optional[str] = None,
        document_name: Optional[str] = None,
        audit_storage_path: Optional[str] = None,
        audit_filename: Optional[str] = None,
        quality_report: Optional[dict] = None,
        estimated_wait: Optional[str] = None,
        user_email: Optional[str] = None,
    ):
        self.id = job_id
        self.user_id = user_id
        self.topic = topic
        self.report_type = report_type
        self.domain = domain
        self.custom_prompt = custom_prompt
        self.included_sources = included_sources or []
        self.status = status
        now_iso = datetime.now(timezone.utc).isoformat()
        self.created_at = created_at or now_iso
        self.created_timestamp = time.time() if not created_at else datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
        self.updated_at = updated_at or now_iso
        self.attempts = attempts
        self.next_retry_at = next_retry_at
        self.error_reason = error_reason
        self.document_base64 = document_base64
        self.document_name = document_name
        self.audit_storage_path = audit_storage_path
        self.audit_filename = audit_filename
        self.quality_report = quality_report
        self.estimated_wait = estimated_wait
        self.user_email = user_email

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "topic": self.topic,
            "report_type": self.report_type,
            "domain": self.domain,
            "custom_prompt": self.custom_prompt,
            "included_sources_count": len(self.included_sources),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "attempts": self.attempts,
            "error_reason": self.error_reason,
            "document_name": self.document_name,
            "has_document": bool(self.document_base64),
            "audit_storage_path": self.audit_storage_path,
            "audit_filename": self.audit_filename,
            "estimated_wait": self.estimated_wait,
            "quality_report": self.quality_report,
        }


class ReportQueueManager:
    """Manages queued report lifecycle, exponential backoff retries, timeouts, and notifications."""
    def __init__(self, config: Optional[ReportQueueConfig] = None, database: Optional[Any] = None):
        self.config = config or default_queue_config
        self.database = database
        self._jobs: Dict[str, QueuedReportJob] = {}

    def enqueue(
        self,
        user_id: str,
        topic: str,
        report_type: str = "proposal",
        domain: str = "scholarly",
        custom_prompt: Optional[str] = None,
        included_sources: Optional[list] = None,
        initial_error: Optional[str] = None,
        audit_storage_path: Optional[str] = None,
        audit_filename: Optional[str] = None,
        user_email: Optional[str] = None,
        immediate_retry: bool = False,
    ) -> QueuedReportJob:
        job_id = str(uuid4())
        now = time.time()
        job = QueuedReportJob(
            job_id=job_id,
            user_id=user_id,
            topic=topic,
            report_type=report_type,
            domain=domain,
            custom_prompt=custom_prompt,
            included_sources=included_sources or [],
            status="queued",
            created_at=datetime.now(timezone.utc).isoformat(),
            attempts=1 if initial_error else 0,
            next_retry_at=now if immediate_retry else now + self.config.initial_backoff_seconds,
            error_reason=initial_error,
            audit_storage_path=audit_storage_path,
            audit_filename=audit_filename,
            estimated_wait=self.config.estimated_wait_range,
            user_email=user_email,
        )
        self._jobs[job_id] = job
        logger.info("Enqueued report job %s for user %s on topic '%s'", job_id, user_id, topic)
        return job

    def get_job(self, job_id: str) -> Optional[QueuedReportJob]:
        return self._jobs.get(job_id)

    def list_jobs(self, user_id: Optional[str] = None) -> List[QueuedReportJob]:
        if user_id:
            return [j for j in self._jobs.values() if j.user_id == user_id]
        return list(self._jobs.values())

    def update_job_status(self, job_id: str, status: str, error_reason: Optional[str] = None) -> Optional[QueuedReportJob]:
        job = self.get_job(job_id)
        if not job:
            return None
        job.status = status
        job.updated_at = datetime.now(timezone.utc).isoformat()
        if error_reason:
            job.error_reason = error_reason
        return job

    def mark_ready(
        self,
        job_id: str,
        document_bytes: bytes,
        document_name: str,
        quality_report: Optional[dict] = None,
    ) -> Optional[QueuedReportJob]:
        job = self.get_job(job_id)
        if not job:
            return None
        job.status = "ready"
        job.updated_at = datetime.now(timezone.utc).isoformat()
        job.document_base64 = base64.b64encode(document_bytes).decode("ascii")
        job.document_name = document_name
        job.quality_report = quality_report
        job.error_reason = None
        
        # Notify user
        NotificationService.notify_report_ready(
            user_id=job.user_id,
            report_id=job.id,
            topic=job.topic,
            user_email=job.user_email,
        )
        logger.info("Report job %s marked ready and user notified", job_id)
        return job

    def mark_failed(self, job_id: str, reason: str) -> Optional[QueuedReportJob]:
        job = self.get_job(job_id)
        if not job:
            return None
        job.status = "failed"
        job.updated_at = datetime.now(timezone.utc).isoformat()
        job.error_reason = reason
        
        # Notify user with retry action
        retry_payload = {
            "topic": job.topic,
            "report_type": job.report_type,
            "domain": job.domain,
            "custom_prompt": job.custom_prompt,
            "included_sources": job.included_sources,
        }
        NotificationService.notify_report_failed(
            user_id=job.user_id,
            report_id=job.id,
            topic=job.topic,
            reason=reason,
            retry_payload=retry_payload,
            user_email=job.user_email,
        )
        logger.info("Report job %s marked failed (reason: %s) and user notified", job_id, reason)
        return job

    def retry_job(self, job_id: str) -> Optional[QueuedReportJob]:
        job = self.get_job(job_id)
        if not job:
            return None
        job.status = "queued"
        job.attempts = 0
        job.error_reason = None
        job.created_at = datetime.now(timezone.utc).isoformat()
        job.created_timestamp = time.time()
        job.updated_at = job.created_at
        job.next_retry_at = time.time()
        logger.info("Manual retry triggered for report job %s", job_id)
        return job

    def process_pending_jobs(self, max_jobs: int = 10) -> List[QueuedReportJob]:
        """Runs a background processing pass for queued jobs."""
        from app.agents.scribe_agent import ScribeResearchAgent
        from app.reports.dossier_generator import DossierGenerator

        now = time.time()
        processed = []
        for job in list(self._jobs.values()):
            if job.status not in ("queued", "generating"):
                continue

            # Check timeout window
            if (now - job.created_timestamp) > self.config.timeout_window_seconds:
                self.mark_failed(job.id, f"Report timed out after {int(self.config.timeout_window_seconds)}s in queue.")
                processed.append(job)
                continue

            # Check if eligible for retry attempt
            if now < job.next_retry_at:
                continue

            # Check max attempts limit
            if job.attempts >= self.config.max_retries:
                self.mark_failed(job.id, f"Maximum retry attempts ({self.config.max_retries}) exceeded.")
                processed.append(job)
                continue

            # Attempt synthesis
            job.status = "generating"
            job.attempts += 1
            job.updated_at = datetime.now(timezone.utc).isoformat()

            try:
                dossier = DossierGenerator().generate_comprehensive_dossier(
                    query=job.topic,
                    included_sources=job.included_sources,
                    custom_prompt=job.custom_prompt,
                    domain=job.domain,
                    report_type=job.report_type,
                )
                scribe = ScribeResearchAgent()
                with tempfile.TemporaryDirectory(prefix="nexus-queued-report-") as report_dir:
                    if job.report_type == "full_starter":
                        report_file = scribe.generate_complete_literature_review(
                            topic=job.topic,
                            included_sources=job.included_sources,
                            dossier=dossier,
                            domain=job.domain,
                            output_directory=report_dir,
                        )
                    else:
                        report_file = scribe.generate_apa_dossier_report(
                            topic=job.topic,
                            included_sources=job.included_sources,
                            dossier=dossier,
                            domain=job.domain,
                            output_directory=report_dir,
                        )
                    report_path = Path(report_file).resolve(strict=True)
                    doc_bytes = report_path.read_bytes()
                    self.mark_ready(
                        job.id,
                        document_bytes=doc_bytes,
                        document_name=report_path.name,
                        quality_report=getattr(dossier, "quality_report", None),
                    )
                    processed.append(job)
            except Exception as e:
                logger.warning("Synthesis attempt %s failed for job %s: %s", job.attempts, job.id, e)
                job.error_reason = str(e)
                if job.attempts >= self.config.max_retries:
                    self.mark_failed(job.id, f"Synthesis provider failed after {job.attempts} attempts: {e}")
                else:
                    # Exponential backoff calculation
                    delay = min(
                        self.config.initial_backoff_seconds * (self.config.backoff_multiplier ** (job.attempts - 1)),
                        self.config.max_backoff_seconds,
                    )
                    job.status = "queued"
                    job.next_retry_at = time.time() + delay
                processed.append(job)

        return processed

    def clear(self) -> None:
        self._jobs.clear()


# Global default queue manager
global_queue_manager = ReportQueueManager()
