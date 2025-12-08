"""Background workers for expiration checks and webhook execution."""
from typing import Optional, Callable
import asyncio
import time
import logging

from server.scheduler import Scheduler
from server.database import Database
from server.webhook_executor import WebhookExecutor

logger = logging.getLogger("runagent_pulse.workers")


class _BaseWorker:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None

    async def start(self, factory: Callable[[], asyncio.Task]):
        if self._task:
            return
        self._task = factory()

    async def stop(self):
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None


class ExpirationWorker(_BaseWorker):
    """Periodically expire unclaimed tasks."""

    def __init__(self, scheduler: Scheduler, interval_seconds: int = 30, max_age_seconds: int = 60):
        super().__init__()
        self.scheduler = scheduler
        self.interval_seconds = interval_seconds
        self.max_age_seconds = max_age_seconds

    async def start(self):
        await super().start(lambda: asyncio.create_task(self._run()))

    async def _run(self):
        while True:
            try:
                await self.scheduler.expire_unclaimed_tasks(max_age_seconds=self.max_age_seconds)
            except Exception as exc:  # pragma: no cover - log and continue
                logger.error("Error in expiration worker: %s", exc)
            await asyncio.sleep(self.interval_seconds)


class WebhookWorker(_BaseWorker):
    """Process due webhook tasks with retries."""

    def __init__(
        self,
        db: Database,
        scheduler: Scheduler,
        webhook_executor: WebhookExecutor,
        interval_seconds: int,
        default_retries: int,
    ):
        super().__init__()
        self.db = db
        self.scheduler = scheduler
        self.webhook_executor = webhook_executor
        self.interval_seconds = interval_seconds
        self.default_retries = default_retries

    async def start(self):
        await super().start(lambda: asyncio.create_task(self._run()))

    async def _run(self):
        worker_id = "webhook-worker"
        while True:
            try:
                current_time = int(time.time())
                tasks = await self.db.get_due_webhook_tasks(current_time, limit=100)

                for task in tasks:
                    task_id = task["task_id"]
                    metadata = task.get("metadata") or {}
                    max_retries = metadata.get("webhook_retries", self.default_retries)
                    attempts = metadata.get("webhook_attempts", 0)

                    if attempts >= max_retries:
                        metadata["webhook_final_failure"] = True
                        await self.db.update_task(task_id, {"metadata": metadata})
                        await self.scheduler.acknowledge_task(
                            task_id=task_id,
                            status="failed",
                            error="max retries exceeded",
                            worker_id=worker_id,
                            execution_id=None,
                        )
                        continue

                    execution_id = await self.scheduler.claim_task(task_id, worker_id)
                    if not execution_id:
                        continue

                    success, error_message = await self.webhook_executor.execute_webhook(task, execution_id)

                    if success:
                        if attempts:
                            metadata["webhook_attempts"] = 0
                            await self.db.update_task(task_id, {"metadata": metadata})
                        await self.scheduler.acknowledge_task(
                            task_id=task_id,
                            status="success",
                            worker_id=worker_id,
                            execution_id=execution_id,
                        )
                        continue

                    attempts += 1
                    metadata["webhook_attempts"] = attempts

                    await self.db.record_execution(
                        task_id=task_id,
                        execution_id=execution_id,
                        executed_at=int(time.time()),
                        status="failed",
                        error=error_message,
                    )

                    if attempts >= max_retries:
                        metadata["webhook_final_failure"] = True
                        await self.db.update_task(task_id, {"metadata": metadata})
                        await self.scheduler.acknowledge_task(
                            task_id=task_id,
                            status="failed",
                            error=error_message,
                            worker_id=worker_id,
                            execution_id=execution_id,
                        )
                        continue

                    # Exponential backoff (1s, 2s, 4s, capped at 60s)
                    backoff_seconds = min(2 ** (attempts - 1), 60)
                    next_run = int(time.time()) + backoff_seconds

                    await self.db.update_task(
                        task_id,
                        {
                            "status": "active",
                            "next_execution": next_run,
                            "metadata": metadata,
                        },
                    )
                    await self.db.add_to_time_bucket(next_run, task_id)

            except Exception as exc:  # pragma: no cover - log and continue
                logger.error("Error in webhook worker: %s", exc)

            await asyncio.sleep(self.interval_seconds)


