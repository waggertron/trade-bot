"""Tests for AsyncWorkerPool — generic concurrent work queue."""

from __future__ import annotations

import asyncio

import pytest

from src.processing.protocols import Processor
from src.processing.worker_pool import AsyncWorkerPool


class _CollectingProcessor:
    """Test processor that records every item it processes."""

    def __init__(self, delay: float = 0.0) -> None:
        self.processed: list[int] = []
        self._delay = delay

    @property
    def name(self) -> str:
        return "collecting"

    async def process(self, item: int) -> None:
        if self._delay:
            await asyncio.sleep(self._delay)
        self.processed.append(item)


class _FailingProcessor:
    """Test processor that raises on certain items."""

    def __init__(self, fail_on: set[int]) -> None:
        self.processed: list[int] = []
        self._fail_on = fail_on

    @property
    def name(self) -> str:
        return "failing"

    async def process(self, item: int) -> None:
        if item in self._fail_on:
            raise ValueError(f"Intentional failure on {item}")
        self.processed.append(item)


class TestAsyncWorkerPoolProtocol:
    def test_processor_satisfies_protocol(self):
        proc = _CollectingProcessor()
        assert isinstance(proc, Processor)


class TestSingleWorker:
    @pytest.mark.asyncio
    async def test_processes_all_submitted_items(self):
        proc = _CollectingProcessor()
        pool = AsyncWorkerPool(proc, workers=1)
        async with pool:
            for i in range(5):
                await pool.submit(i)
        assert sorted(proc.processed) == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_processed_count_matches(self):
        proc = _CollectingProcessor()
        pool = AsyncWorkerPool(proc, workers=1)
        async with pool:
            for i in range(3):
                await pool.submit(i)
        assert pool.processed_count == 3

    @pytest.mark.asyncio
    async def test_empty_queue_exits_cleanly(self):
        proc = _CollectingProcessor()
        pool = AsyncWorkerPool(proc, workers=1)
        async with pool:
            pass  # nothing submitted
        assert pool.processed_count == 0

    @pytest.mark.asyncio
    async def test_error_in_item_does_not_kill_pool(self):
        proc = _FailingProcessor(fail_on={2})
        pool = AsyncWorkerPool(proc, workers=1)
        async with pool:
            for i in range(5):
                await pool.submit(i)
        assert sorted(proc.processed) == [0, 1, 3, 4]
        assert pool.error_count == 1

    @pytest.mark.asyncio
    async def test_error_count_tracks_failures(self):
        proc = _FailingProcessor(fail_on={0, 2, 4})
        pool = AsyncWorkerPool(proc, workers=1)
        async with pool:
            for i in range(5):
                await pool.submit(i)
        assert pool.error_count == 3
        assert pool.processed_count == 2


class TestMultipleWorkers:
    @pytest.mark.asyncio
    async def test_multiple_workers_all_items_processed(self):
        proc = _CollectingProcessor()
        pool = AsyncWorkerPool(proc, workers=4)
        async with pool:
            for i in range(20):
                await pool.submit(i)
        assert sorted(proc.processed) == list(range(20))

    @pytest.mark.asyncio
    async def test_multiple_workers_faster_than_single(self):
        """4 workers with 0.05s delay should be faster than 1 worker for 8 items."""
        import time

        proc1 = _CollectingProcessor(delay=0.05)
        pool1 = AsyncWorkerPool(proc1, workers=1)
        t0 = time.monotonic()
        async with pool1:
            for i in range(8):
                await pool1.submit(i)
        single_time = time.monotonic() - t0

        proc4 = _CollectingProcessor(delay=0.05)
        pool4 = AsyncWorkerPool(proc4, workers=4)
        t0 = time.monotonic()
        async with pool4:
            for i in range(8):
                await pool4.submit(i)
        multi_time = time.monotonic() - t0

        assert multi_time < single_time * 0.8  # at least 20% faster

    @pytest.mark.asyncio
    async def test_workers_count_is_configurable(self):
        proc = _CollectingProcessor()
        pool = AsyncWorkerPool(proc, workers=3)
        assert pool.workers == 3


class TestDrain:
    @pytest.mark.asyncio
    async def test_drain_waits_for_all_items(self):
        proc = _CollectingProcessor(delay=0.01)
        pool = AsyncWorkerPool(proc, workers=2)
        await pool.start()
        for i in range(10):
            await pool.submit(i)
        await pool.drain()
        assert len(proc.processed) == 10
        await pool.stop()

    @pytest.mark.asyncio
    async def test_context_manager_drains_on_exit(self):
        proc = _CollectingProcessor(delay=0.01)
        pool = AsyncWorkerPool(proc, workers=2)
        async with pool:
            for i in range(5):
                await pool.submit(i)
        # After context exit, all items must be processed
        assert len(proc.processed) == 5
