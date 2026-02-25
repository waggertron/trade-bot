"""Tests that FeedManager fetches concurrently with bounded parallelism."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.feeds.manager import FeedManager


class FakeFeed:
    def __init__(self, name: str, feed_type: str = "rss"):
        self.name = name
        self.feed_type = feed_type
        self.url = f"https://example.com/{name}"
        self.id = name


def _make_mock_adapter(fetch_side_effect):
    """Create a mock adapter with the given fetch_articles side effect."""
    adapter = MagicMock()
    adapter.fetch_articles = AsyncMock(side_effect=fetch_side_effect)
    return adapter


@pytest.fixture
def manager():
    db = AsyncMock()
    mgr = FeedManager(db)
    mgr.feeds_by_type = {
        "rss": [FakeFeed("feed1"), FakeFeed("feed2")],
    }
    return mgr


class TestParallelFetch:
    async def test_fetches_symbols_concurrently(self, manager: FeedManager):
        """Multiple symbols should be fetched concurrently, not sequentially."""
        loop = asyncio.get_event_loop()
        start = loop.time()

        async def slow_fetch(symbol: str):
            await asyncio.sleep(0.2)
            return []

        mock_adapter = _make_mock_adapter(slow_fetch)

        # 10 symbols * 0.2s = 2.0s sequential, ~0.2s concurrent
        symbols = [f"SYM{i}" for i in range(10)]

        with patch(
            "src.providers.rss.RSSNewsProvider.from_feed_records",
            return_value=mock_adapter,
        ):
            await manager.fetch_all(symbols)

        total_time = loop.time() - start
        # Sequential would be >= 2.0s. Concurrent should be well under 1.0s.
        assert total_time < 1.0, (
            f"Fetch took {total_time:.2f}s — appears sequential, not concurrent"
        )

    async def test_semaphore_limits_concurrency(self, manager: FeedManager):
        """Concurrency should be bounded by a semaphore."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def tracking_fetch(symbol: str):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)
            await asyncio.sleep(0.05)
            async with lock:
                current_concurrent -= 1
            return []

        mock_adapter = _make_mock_adapter(tracking_fetch)

        symbols = [f"SYM{i}" for i in range(20)]

        with patch(
            "src.providers.rss.RSSNewsProvider.from_feed_records",
            return_value=mock_adapter,
        ):
            await manager.fetch_all(symbols)

        assert max_concurrent <= 10, (
            f"Max concurrency was {max_concurrent} — should be bounded by semaphore"
        )

    async def test_error_in_one_symbol_does_not_block_others(self, manager: FeedManager):
        """An error fetching one symbol should not prevent others from completing."""
        call_count = 0

        async def failing_fetch(symbol: str):
            nonlocal call_count
            call_count += 1
            if symbol == "FAIL":
                raise RuntimeError("Network error")
            return [MagicMock(title=f"Article for {symbol}")]

        mock_adapter = _make_mock_adapter(failing_fetch)

        symbols = ["AAPL", "FAIL", "GOOGL"]

        with patch(
            "src.providers.rss.RSSNewsProvider.from_feed_records",
            return_value=mock_adapter,
        ):
            articles = await manager.fetch_all(symbols)

        assert call_count == 3
        assert len(articles) == 2
