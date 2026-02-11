"""Mock implementations of all provider protocols for testing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from src.core.models import AssetType, MarketTick
from src.sentiment.models import SentimentResult
from src.db.models import SignalRecord, TradeRecord
from src.providers.configs import (
    MockFeatureConfig,
    MockMarketConfig,
    MockNewsConfig,
    MockOnChainConfig,
    MockSentimentConfig,
)
from src.providers.protocols import HttpResponse


# -- Mock HttpClient ----------------------------------------------------------


class MockHttpClient:
    """Mock HTTP client that returns stubbed responses and tracks calls."""

    def __init__(self) -> None:
        self._stubs: dict[str, HttpResponse] = {}
        self.calls: list[dict[str, Any]] = []

    def stub(self, url: str, response: HttpResponse) -> None:
        """Register a canned response for a URL."""
        self._stubs[url] = response

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        self.calls.append({"method": "GET", "url": url, "kwargs": kwargs})
        if url in self._stubs:
            return self._stubs[url]
        return HttpResponse(404, '{"error": "not found"}')

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        self.calls.append({"method": "POST", "url": url, "kwargs": kwargs})
        if url in self._stubs:
            return self._stubs[url]
        return HttpResponse(404, '{"error": "not found"}')

    async def close(self) -> None:
        self.calls.append({"method": "CLOSE"})


# -- Mock MarketDataProvider --------------------------------------------------


class MockMarketDataProvider:
    """Mock market data provider with configurable prices."""

    def __init__(self, config: MockMarketConfig | None = None) -> None:
        self._config = config or MockMarketConfig()
        self._prices: dict[str, Decimal] = {}
        self.get_ticks_count: int = 0

        # Seed from config default_prices
        for sym, price_str in self._config.default_prices.items():
            self._prices[sym] = Decimal(price_str)

    @property
    def name(self) -> str:
        return "mock_market"

    def set_price(self, symbol: str, price: Decimal) -> None:
        """Set the price returned for a given symbol."""
        self._prices[symbol] = price

    async def get_ticks(self, symbols: list[str]) -> list[MarketTick]:
        self.get_ticks_count += 1
        if self._config.should_fail:
            raise RuntimeError("MockMarketDataProvider configured to fail")
        if self._config.latency_ms > 0:
            await asyncio.sleep(self._config.latency_ms / 1000.0)
        ticks: list[MarketTick] = []
        now = datetime.now(timezone.utc)
        for sym in symbols:
            price = self._prices.get(sym, Decimal("100.00"))
            ticks.append(
                MarketTick(
                    symbol=sym,
                    price=price,
                    volume=0,
                    timestamp=now,
                    asset_type=AssetType.CRYPTO,
                )
            )
        return ticks

    async def get_ohlc(
        self, symbol: str, interval: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        if self._config.should_fail:
            raise RuntimeError("MockMarketDataProvider configured to fail")
        return []

    async def health_check(self) -> bool:
        return not self._config.should_fail


# -- Mock NewsProvider --------------------------------------------------------


class MockNewsProvider:
    """Mock news provider with configurable articles."""

    def __init__(self, config: MockNewsConfig | None = None) -> None:
        self._config = config or MockNewsConfig()
        self.fetch_count: int = 0

    @property
    def name(self) -> str:
        return "mock_news"

    async def fetch_articles(self, symbol: str, limit: int = 10) -> list[Any]:
        self.fetch_count += 1
        if self._config.should_fail:
            raise RuntimeError("MockNewsProvider configured to fail")
        if self._config.latency_ms > 0:
            await asyncio.sleep(self._config.latency_ms / 1000.0)
        return self._config.canned_articles[:limit]

    async def health_check(self) -> bool:
        return not self._config.should_fail

    @property
    def rate_limit(self) -> int:
        return self._config.max_articles_per_fetch


# -- Mock SentimentAnalyzer ---------------------------------------------------


class MockSentimentAnalyzer:
    """Mock sentiment analyzer returning configured scores."""

    def __init__(self, config: MockSentimentConfig | None = None) -> None:
        self._config = config or MockSentimentConfig()
        self.score_count: int = 0

    @property
    def name(self) -> str:
        return "mock_sentiment"

    async def score(self, text: str) -> SentimentResult:
        self.score_count += 1
        if self._config.should_fail:
            raise RuntimeError("MockSentimentAnalyzer configured to fail")
        return SentimentResult(
            score=self._config.default_score,
            magnitude=self._config.default_magnitude,
            timestamp=datetime.now(timezone.utc),
            reasoning=None,
        )

    async def score_batch(self, texts: list[str]) -> list[SentimentResult]:
        results: list[SentimentResult] = []
        for text in texts:
            results.append(await self.score(text))
        return results


# -- Mock OnChainProvider -----------------------------------------------------


class MockOnChainProvider:
    """Mock on-chain provider."""

    def __init__(self, config: MockOnChainConfig | None = None) -> None:
        self._config = config or MockOnChainConfig()

    @property
    def name(self) -> str:
        return "mock_onchain"

    async def get_metrics(self, symbol: str) -> dict[str, Any]:
        if self._config.should_fail:
            raise RuntimeError("MockOnChainProvider configured to fail")
        return {"symbol": symbol, "mock": True}

    async def health_check(self) -> bool:
        return not self._config.should_fail


# -- Mock FeatureProvider -----------------------------------------------------


class MockFeatureProvider:
    """Mock feature provider with configurable output."""

    def __init__(self, config: MockFeatureConfig | None = None) -> None:
        self._config = config or MockFeatureConfig()
        self._features: dict[str, float] = dict(self._config.default_features)

    @property
    def name(self) -> str:
        return "mock_feature"

    def set_features(self, features: dict[str, float]) -> None:
        """Set the features returned by compute()."""
        self._features = features

    @property
    def required_inputs(self) -> list[str]:
        return ["price", "volume"]

    async def compute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return dict(self._features)


# -- Mock DataStore -----------------------------------------------------------


class MockDataStore:
    """In-memory mock data store."""

    def __init__(self) -> None:
        self._trades: list[TradeRecord] = []
        self._signals: list[SignalRecord] = []

    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def save_trade(self, trade: TradeRecord) -> str:
        self._trades.append(trade)
        return trade.id

    async def list_trades(
        self, strategy: str | None = None, limit: int = 100
    ) -> list[TradeRecord]:
        trades = self._trades
        if strategy is not None:
            trades = [t for t in trades if t.strategy == strategy]
        return trades[:limit]

    async def save_signal(self, signal: SignalRecord) -> str:
        self._signals.append(signal)
        return signal.id

    async def list_signals(self, limit: int = 100) -> list[SignalRecord]:
        return self._signals[:limit]
