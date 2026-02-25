"""Tests for stock feed wiring with mock/real fallback."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.core.config import Settings


def test_null_stock_feed_importable_from_module():
    """NullStockFeed should be importable from src.feeds.null_feed."""
    from src.feeds.null_feed import NullStockFeed

    feed = NullStockFeed()
    assert feed is not None


@pytest.mark.asyncio
async def test_null_stock_feed_returns_zero_price():
    from src.feeds.null_feed import NullStockFeed

    feed = NullStockFeed()
    price = await feed.get_price("AAPL")
    assert price == Decimal("0")


@pytest.mark.asyncio
async def test_null_stock_feed_returns_empty_order_book():
    from src.feeds.null_feed import NullStockFeed

    feed = NullStockFeed()
    book = await feed.get_order_book("AAPL")
    assert book == {"bids": [], "asks": []}


def test_mock_true_uses_null_feed():
    """When use_mocks.stock_feed=True, build_stock_feed returns NullStockFeed."""
    from main import build_stock_feed
    from src.feeds.null_feed import NullStockFeed

    settings = Settings.for_testing(use_mocks={"stock_feed": True})
    feed, symbols = build_stock_feed(settings)
    assert isinstance(feed, NullStockFeed)
    assert symbols == []


def test_mock_false_uses_ibkr_feed():
    """When use_mocks.stock_feed=False, build_stock_feed returns IBKRFeed."""
    from main import build_stock_feed
    from src.integrations.ibkr import IBKRFeed

    settings = Settings.for_testing(
        use_mocks={"stock_feed": False},
        trading={"symbols": {"stocks": ["AAPL", "MSFT"], "crypto": ["BTC/USD"]}},
    )
    feed, symbols = build_stock_feed(settings)
    assert isinstance(feed, IBKRFeed)
    assert symbols == ["AAPL", "MSFT"]
