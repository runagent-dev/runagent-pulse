"""Expiration worker - periodically expire unclaimed tasks."""
import asyncio
import logging

from server.workers.base import BaseWorker
from server.scheduler import Scheduler

logger = logging.getLogger("runagent_pulse.workers.expiration")


class ExpirationWorker(BaseWorker):
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

