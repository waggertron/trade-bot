"""Tests for mock provider implementations."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.db.models import SignalRecord, TradeRecord
from src.providers.configs import MockMarketConfig, MockSentimentConfig
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
from src.sentiment.models import SentimentResult

# -- MockHttpClient -----------------------------------------------------------


class TestMockHttpClient:
    def test_implements_protocol(self):
        assert isinstance(MockHttpClient(), HttpClient)

    async def test_stub_returns_canned_response(self):
        client = MockHttpClient()
        client.stub("https://example.com", HttpResponse(200, '{"ok": true}'))
        resp = await client.get("https://example.com")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    async def test_records_calls(self):
        client = MockHttpClient()
        client.stub("https://example.com", HttpResponse(200, "{}"))
        await client.get("https://example.com")
        await client.post("https://example.com", data="test")
        await client.close()
        assert len(client.calls) == 3
        assert client.calls[0]["method"] == "GET"
        assert client.calls[1]["method"] == "POST"
        assert client.calls[2]["method"] == "CLOSE"

    async def test_unstubbed_returns_404(self):
        client = MockHttpClient()
        resp = await client.get("https://unknown.com")
        assert resp.status_code == 404


# -- MockMarketDataProvider ---------------------------------------------------


class TestMockMarketDataProvider:
    def test_implements_protocol(self):
        assert isinstance(MockMarketDataProvider(), MarketDataProvider)

    async def test_set_price_returns_ticks(self):
        provider = MockMarketDataProvider()
        provider.set_price("BTC", Decimal("50000.00"))
        ticks = await provider.get_ticks(["BTC"])
        assert len(ticks) == 1
        assert ticks[0].symbol == "BTC"
        assert ticks[0].price == Decimal("50000.00")

    async def test_health_check(self):
        provider = MockMarketDataProvider()
        assert await provider.health_check() is True

    async def test_health_check_when_failing(self):
        provider = MockMarketDataProvider(MockMarketConfig(should_fail=True))
        assert await provider.health_check() is False

    async def test_tracks_count(self):
        provider = MockMarketDataProvider()
        assert provider.get_ticks_count == 0
        await provider.get_ticks(["BTC"])
        await provider.get_ticks(["ETH"])
        assert provider.get_ticks_count == 2

    async def test_should_fail_raises(self):
        provider = MockMarketDataProvider(MockMarketConfig(should_fail=True))
        with pytest.raises(RuntimeError, match="configured to fail"):
            await provider.get_ticks(["BTC"])

    async def test_default_prices_from_config(self):
        provider = MockMarketDataProvider(MockMarketConfig(default_prices={"ETH": "3000.00"}))
        ticks = await provider.get_ticks(["ETH"])
        assert ticks[0].price == Decimal("3000.00")


# -- MockNewsProvider ---------------------------------------------------------


class TestMockNewsProvider:
    def test_implements_protocol(self):
        assert isinstance(MockNewsProvider(), NewsProvider)

    async def test_basic_fetch(self):
        provider = MockNewsProvider()
        articles = await provider.fetch_articles("BTC")
        assert articles == []
        assert provider.fetch_count == 1

    async def test_should_fail_raises(self):
        from src.providers.configs import MockNewsConfig

        provider = MockNewsProvider(MockNewsConfig(should_fail=True))
        with pytest.raises(RuntimeError, match="configured to fail"):
            await provider.fetch_articles("BTC")


# -- MockSentimentAnalyzer ----------------------------------------------------


class TestMockSentimentAnalyzer:
    def test_implements_protocol(self):
        assert isinstance(MockSentimentAnalyzer(), SentimentAnalyzer)

    async def test_returns_configured_score(self):
        config = MockSentimentConfig(default_score=0.8, default_magnitude=0.9)
        analyzer = MockSentimentAnalyzer(config)
        result = await analyzer.score("Bitcoin is great")
        assert isinstance(result, SentimentResult)
        assert result.score == 0.8
        assert result.magnitude == 0.9

    async def test_tracks_score_count(self):
        analyzer = MockSentimentAnalyzer()
        await analyzer.score("text1")
        await analyzer.score("text2")
        assert analyzer.score_count == 2

    async def test_score_batch(self):
        analyzer = MockSentimentAnalyzer()
        results = await analyzer.score_batch(["a", "b", "c"])
        assert len(results) == 3
        assert analyzer.score_count == 3

    async def test_should_fail_raises(self):
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(should_fail=True))
        with pytest.raises(RuntimeError, match="configured to fail"):
            await analyzer.score("text")


# -- MockOnChainProvider ------------------------------------------------------


class TestMockOnChainProvider:
    def test_implements_protocol(self):
        assert isinstance(MockOnChainProvider(), OnChainProvider)

    async def test_basic_metrics(self):
        provider = MockOnChainProvider()
        metrics = await provider.get_metrics("BTC")
        assert metrics["symbol"] == "BTC"

    async def test_should_fail_raises(self):
        from src.providers.configs import MockOnChainConfig

        provider = MockOnChainProvider(MockOnChainConfig(should_fail=True))
        with pytest.raises(ConnectionError, match="Mock on-chain provider failure"):
            await provider.get_metrics("BTC")


# -- MockFeatureProvider ------------------------------------------------------


class TestMockFeatureProvider:
    def test_implements_protocol(self):
        assert isinstance(MockFeatureProvider(), FeatureProvider)

    async def test_set_features(self):
        provider = MockFeatureProvider()
        provider.set_features({"sma": 1.0, "rsi": 55.0})
        result = await provider.compute({"price": [1, 2, 3]})
        assert result == {"sma": 1.0, "rsi": 55.0}

    def test_required_inputs(self):
        provider = MockFeatureProvider()
        assert provider.required_inputs == ["price", "volume"]


# -- MockDataStore ------------------------------------------------------------


class TestMockDataStore:
    def test_implements_protocol(self):
        assert isinstance(MockDataStore(), DataStore)

    async def test_save_and_list_trades_roundtrip(self):
        store = MockDataStore()
        await store.initialize()

        trade = TradeRecord(
            symbol="BTC",
            side="buy",
            quantity="1.0",
            price="50000.00",
            commission="10.00",
            strategy="momentum",
            paper=True,
            timestamp=datetime.now(UTC),
        )
        trade_id = await store.save_trade(trade)
        assert trade_id == trade.id

        trades = await store.list_trades()
        assert len(trades) == 1
        assert trades[0].symbol == "BTC"

    async def test_save_and_list_signals_roundtrip(self):
        store = MockDataStore()
        await store.initialize()

        signal = SignalRecord(
            symbol="ETH",
            direction="buy",
            confidence=0.85,
            strategy="sentiment",
            reasoning="bullish news",
            timestamp=datetime.now(UTC),
        )
        signal_id = await store.save_signal(signal)
        assert signal_id == signal.id

        signals = await store.list_signals()
        assert len(signals) == 1
        assert signals[0].symbol == "ETH"

    async def test_list_trades_by_strategy(self):
        store = MockDataStore()
        now = datetime.now(UTC)

        await store.save_trade(
            TradeRecord(
                symbol="BTC",
                side="buy",
                quantity="1",
                price="50000",
                commission="0",
                strategy="momentum",
                paper=True,
                timestamp=now,
            )
        )
        await store.save_trade(
            TradeRecord(
                symbol="ETH",
                side="sell",
                quantity="10",
                price="3000",
                commission="0",
                strategy="sentiment",
                paper=True,
                timestamp=now,
            )
        )

        momentum_trades = await store.list_trades(strategy="momentum")
        assert len(momentum_trades) == 1
        assert momentum_trades[0].strategy == "momentum"


# -- SentimentResult model ----------------------------------------------------


class TestSentimentResult:
    def test_creates_valid(self):
        result = SentimentResult(
            score=0.5,
            magnitude=0.8,
            timestamp=datetime.now(UTC),
            reasoning="positive outlook",
        )
        assert result.score == 0.5
        assert result.magnitude == 0.8

    def test_frozen(self):
        result = SentimentResult(
            score=0.5,
            magnitude=0.8,
            timestamp=datetime.now(UTC),
        )
        with pytest.raises(ValidationError):
            result.score = 0.9  # type: ignore[misc]

    def test_rejects_out_of_range_score(self):
        with pytest.raises(ValidationError):
            SentimentResult(
                score=1.5,
                magnitude=0.5,
                timestamp=datetime.now(UTC),
            )
