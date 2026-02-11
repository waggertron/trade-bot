"""Protocol compliance test suites.

Each base class defines tests that ANY implementation of a protocol must pass.
Concrete test classes apply them to mock implementations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from src.db.models import SignalRecord, TradeRecord
from src.providers.mock import (
    MockDataStore,
    MockFeatureProvider,
    MockHttpClient,
    MockMarketDataProvider,
    MockNewsProvider,
    MockOnChainProvider,
    MockSentimentAnalyzer,
)
from src.providers.protocols import (
    DataStore,
    FeatureProvider,
    HttpClient,
    HttpResponse,
    MarketDataProvider,
    NewsProvider,
    OnChainProvider,
    SentimentAnalyzer,
)


# ---------------------------------------------------------------------------
# Base compliance classes
# ---------------------------------------------------------------------------


class HttpClientCompliance:
    """Shared tests for any HttpClient implementation."""

    def make_client(self) -> HttpClient:
        raise NotImplementedError

    def test_implements_protocol(self):
        assert isinstance(self.make_client(), HttpClient)

    @pytest.mark.asyncio
    async def test_get_returns_http_response(self):
        client = self.make_client()
        resp = await client.get("https://example.com")
        assert isinstance(resp, HttpResponse)
        assert isinstance(resp.status_code, int)
        assert isinstance(resp.text, str)

    @pytest.mark.asyncio
    async def test_post_returns_http_response(self):
        client = self.make_client()
        resp = await client.post("https://example.com")
        assert isinstance(resp, HttpResponse)
        assert isinstance(resp.status_code, int)

    @pytest.mark.asyncio
    async def test_close_does_not_raise(self):
        client = self.make_client()
        await client.close()  # should not raise


class MarketDataCompliance:
    """Shared tests for any MarketDataProvider."""

    def make_provider(self) -> MarketDataProvider:
        raise NotImplementedError

    def test_implements_protocol(self):
        assert isinstance(self.make_provider(), MarketDataProvider)

    def test_has_name(self):
        assert isinstance(self.make_provider().name, str)
        assert len(self.make_provider().name) > 0

    @pytest.mark.asyncio
    async def test_get_ticks_returns_list(self):
        result = await self.make_provider().get_ticks(["BTC/USD"])
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_ohlc_returns_list(self):
        result = await self.make_provider().get_ohlc("BTC/USD", "1h", limit=10)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self):
        assert isinstance(await self.make_provider().health_check(), bool)


class NewsProviderCompliance:
    """Shared tests for any NewsProvider."""

    def make_provider(self) -> NewsProvider:
        raise NotImplementedError

    def test_implements_protocol(self):
        assert isinstance(self.make_provider(), NewsProvider)

    def test_has_name(self):
        assert isinstance(self.make_provider().name, str)
        assert len(self.make_provider().name) > 0

    @pytest.mark.asyncio
    async def test_fetch_articles_returns_list(self):
        result = await self.make_provider().fetch_articles("BTC/USD")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self):
        assert isinstance(await self.make_provider().health_check(), bool)

    def test_rate_limit_returns_positive_int(self):
        assert isinstance(self.make_provider().rate_limit, int)
        assert self.make_provider().rate_limit > 0


class SentimentAnalyzerCompliance:
    """Shared tests for any SentimentAnalyzer."""

    def make_analyzer(self) -> SentimentAnalyzer:
        raise NotImplementedError

    def test_implements_protocol(self):
        assert isinstance(self.make_analyzer(), SentimentAnalyzer)

    def test_has_name(self):
        assert isinstance(self.make_analyzer().name, str)
        assert len(self.make_analyzer().name) > 0

    @pytest.mark.asyncio
    async def test_score_returns_result(self):
        result = await self.make_analyzer().score("Bitcoin is going up")
        assert result is not None

    @pytest.mark.asyncio
    async def test_score_batch_returns_list(self):
        results = await self.make_analyzer().score_batch(["text1", "text2"])
        assert isinstance(results, list)
        assert len(results) == 2


class DataStoreCompliance:
    """Shared tests for any DataStore."""

    def make_store(self) -> DataStore:
        raise NotImplementedError

    def test_implements_protocol(self):
        assert isinstance(self.make_store(), DataStore)

    @pytest.mark.asyncio
    async def test_initialize_and_close(self):
        store = self.make_store()
        await store.initialize()
        await store.close()

    @pytest.mark.asyncio
    async def test_save_and_list_trades(self):
        store = self.make_store()
        await store.initialize()
        trade = TradeRecord(
            symbol="BTC/USD",
            side="buy",
            quantity="1.0",
            price="50000.00",
            commission="10.00",
            strategy="momentum",
            paper=True,
            timestamp=datetime.now(timezone.utc),
        )
        trade_id = await store.save_trade(trade)
        assert isinstance(trade_id, str)
        assert len(trade_id) > 0

        trades = await store.list_trades()
        assert isinstance(trades, list)
        assert len(trades) >= 1
        await store.close()

    @pytest.mark.asyncio
    async def test_save_and_list_signals(self):
        store = self.make_store()
        await store.initialize()
        signal = SignalRecord(
            symbol="ETH/USD",
            direction="buy",
            confidence=0.85,
            strategy="sentiment",
            reasoning="bullish news",
            timestamp=datetime.now(timezone.utc),
        )
        signal_id = await store.save_signal(signal)
        assert isinstance(signal_id, str)
        assert len(signal_id) > 0

        signals = await store.list_signals()
        assert isinstance(signals, list)
        assert len(signals) >= 1
        await store.close()

    @pytest.mark.asyncio
    async def test_list_trades_with_strategy_filter(self):
        store = self.make_store()
        await store.initialize()
        now = datetime.now(timezone.utc)
        await store.save_trade(
            TradeRecord(
                symbol="BTC/USD", side="buy", quantity="1", price="50000",
                commission="0", strategy="momentum", paper=True, timestamp=now,
            )
        )
        await store.save_trade(
            TradeRecord(
                symbol="ETH/USD", side="sell", quantity="10", price="3000",
                commission="0", strategy="sentiment", paper=True, timestamp=now,
            )
        )
        filtered = await store.list_trades(strategy="momentum")
        assert isinstance(filtered, list)
        assert all(t.strategy == "momentum" for t in filtered)
        await store.close()


# ---------------------------------------------------------------------------
# Concrete compliance test classes (apply to mock implementations)
# ---------------------------------------------------------------------------


class TestMockHttpClientCompliance(HttpClientCompliance):
    def make_client(self):
        client = MockHttpClient()
        client.stub("https://example.com", HttpResponse(200, '{"ok": true}'))
        return client


class TestMockMarketDataCompliance(MarketDataCompliance):
    def make_provider(self):
        provider = MockMarketDataProvider()
        provider.set_price("BTC/USD", Decimal("50000"))
        return provider


class TestMockNewsProviderCompliance(NewsProviderCompliance):
    def make_provider(self):
        return MockNewsProvider()


class TestMockSentimentAnalyzerCompliance(SentimentAnalyzerCompliance):
    def make_analyzer(self):
        return MockSentimentAnalyzer()


class TestMockDataStoreCompliance(DataStoreCompliance):
    def make_store(self):
        return MockDataStore()
