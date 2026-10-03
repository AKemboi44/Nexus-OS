"""Background queue worker for processing queued report jobs."""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class QueueWorker:
    """Runs background processing loop for queued report jobs."""

    def __init__(self, queue_manager, interval_seconds: int = 30, max_jobs_per_cycle: int = 5):
        """
        Args:
            queue_manager: ReportQueueManager instance
            interval_seconds: How often to process jobs
            max_jobs_per_cycle: Max jobs to attempt per cycle
        """
        self.queue_manager = queue_manager
        self.interval_seconds = interval_seconds
        self.max_jobs_per_cycle = max_jobs_per_cycle
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the background worker."""
        if self._running:
            logger.warning("Queue worker already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Queue worker started (interval=%ds, max_jobs=%d)", self.interval_seconds, self.max_jobs_per_cycle)

    async def stop(self):
        """Stop the background worker."""
        self._running = False
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Queue worker stopped")

    async def _run_loop(self):
        """Main worker loop."""
        while self._running:
            try:
                # Process pending jobs
                start_time = time.time()
                processed = self.queue_manager.process_pending_jobs(max_jobs=self.max_jobs_per_cycle)
                elapsed = time.time() - start_time

                if processed:
                    logger.info("Queue worker processed %d job(s) in %.2fs", len(processed), elapsed)

                # Sleep before next cycle
                await asyncio.sleep(self.interval_seconds)

            except asyncio.CancelledError:
                logger.info("Queue worker cancelled")
                break
            except Exception as e:
                logger.exception("Queue worker error (will retry): %s", e)
                # Sleep longer on error to avoid tight loop
                try:
                    await asyncio.sleep(min(self.interval_seconds * 2, 60))
                except asyncio.CancelledError:
                    break


# Global worker instance
_queue_worker: Optional[QueueWorker] = None


def get_queue_worker(queue_manager=None) -> QueueWorker:
    """Get or create the global queue worker."""
    global _queue_worker
    if _queue_worker is None:
        if queue_manager is None:
            from app.reports.report_queue import global_queue_manager
            queue_manager = global_queue_manager
        _queue_worker = QueueWorker(queue_manager)
    return _queue_worker


async def start_queue_worker():
    """Start the global queue worker."""
    worker = get_queue_worker()
    await worker.start()


async def stop_queue_worker():
    """Stop the global queue worker."""
    if _queue_worker:
        await _queue_worker.stop()
