"""Base worker class for all background workers."""
from typing import Optional, Callable
import asyncio


class BaseWorker:
    """Base class for all background workers"""
    
    def __init__(self):
        self._task: Optional[asyncio.Task] = None

    async def start(self, factory: Callable[[], asyncio.Task]):
        """Start the worker"""
        if self._task:
            return
        self._task = factory()

    async def stop(self):
        """Stop the worker"""
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

