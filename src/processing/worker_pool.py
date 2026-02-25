"""AsyncWorkerPool — a generic concurrent work queue backed by asyncio.Queue.

Usage::

    pool = AsyncWorkerPool(my_processor, workers=4)
    async with pool:
        for item in items:
            await pool.submit(item)
    # All items processed here.

Or with explicit lifecycle::

    await pool.start()
    await pool.submit(item)
    await pool.drain()   # wait until queue is empty
    await pool.stop()
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from src.processing.protocols import Processor

T = TypeVar("T")

logger = logging.getLogger(__name__)


class AsyncWorkerPool[T]:
    """Runs *workers* concurrent coroutines that drain a shared asyncio.Queue.

    Parameters
    ----------
    processor:
        Any object satisfying the ``Processor[T]`` protocol.
    workers:
        Number of concurrent worker coroutines.  Default 1.
    """

    def __init__(self, processor: Processor[T], workers: int = 1) -> None:
        self._processor = processor
        self._workers = workers
        self._queue: asyncio.Queue[T] = asyncio.Queue()
        self._processed_count: int = 0
        self._error_count: int = 0
        self._tasks: list[asyncio.Task[None]] = []

    # -- properties -----------------------------------------------------------

    @property
    def workers(self) -> int:
        return self._workers

    @property
    def processed_count(self) -> int:
        return self._processed_count

    @property
    def error_count(self) -> int:
        return self._error_count

    # -- lifecycle ------------------------------------------------------------

    async def start(self) -> None:
        """Spawn worker coroutines."""
        self._tasks = [
            asyncio.create_task(self._worker(), name=f"{self._processor.name}-worker-{i}")
            for i in range(self._workers)
        ]

    async def drain(self) -> None:
        """Block until every submitted item has been processed."""
        await self._queue.join()

    async def stop(self) -> None:
        """Cancel and await all worker tasks."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    # -- context manager ------------------------------------------------------

    async def __aenter__(self) -> AsyncWorkerPool[T]:
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.drain()
        await self.stop()

    # -- submission -----------------------------------------------------------

    async def submit(self, item: T) -> None:
        """Enqueue *item* for processing."""
        await self._queue.put(item)

    # -- internal -------------------------------------------------------------

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()
            try:
                await self._processor.process(item)
                self._processed_count += 1
            except Exception:
                self._error_count += 1
                logger.exception("[%s] Error processing item", self._processor.name)
            finally:
                self._queue.task_done()
