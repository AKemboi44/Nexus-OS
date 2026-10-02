import os
from typing import Optional
from pydantic import BaseModel, Field


class ReportQueueConfig(BaseModel):
    """Configuration for queued report synthesis and retries."""
    estimated_wait_range: str = Field(
        default_factory=lambda: os.getenv("REPORT_ESTIMATED_WAIT_RANGE", "usually under 20 minutes")
    )
    max_retries: int = Field(
        default_factory=lambda: int(os.getenv("REPORT_MAX_RETRIES", "3"))
    )
    initial_backoff_seconds: float = Field(
        default_factory=lambda: float(os.getenv("REPORT_INITIAL_BACKOFF_SECONDS", "2.0"))
    )
    backoff_multiplier: float = Field(
        default_factory=lambda: float(os.getenv("REPORT_BACKOFF_MULTIPLIER", "2.0"))
    )
    max_backoff_seconds: float = Field(
        default_factory=lambda: float(os.getenv("REPORT_MAX_BACKOFF_SECONDS", "300.0"))
    )
    timeout_window_seconds: float = Field(
        default_factory=lambda: float(os.getenv("REPORT_TIMEOUT_WINDOW_SECONDS", "1200.0"))  # 20 minutes default timeout
    )


# Global default configuration instance
default_queue_config = ReportQueueConfig()
