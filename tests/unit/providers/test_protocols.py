"""Tests for provider protocol runtime checkability."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.models import MarketTick
from src.db.models import SignalRecord, TradeRecord
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


# -- Conforming dummy implementations ----------------------------------------


class DummyHttpClient:
    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        return HttpResponse(200, "{}")

    async def post(self, url: str, **kwargs: Any) -> HttpResponse:
        return HttpResponse(200, "{}")

    async def close(self) -> None:
        pass


class DummyMarketDataProvider:
    @property
    def name(self) -> str:
        return "dummy"

    async def get_ticks(self, symbols: list[str]) -> list[MarketTick]:
        return []

    async def get_ohlc(
        self, symbol: str, interval: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        return []

    async def health_check(self) -> bool:
        return True


class DummyNewsProvider:
    @property
    def name(self) -> str:
        return "dummy"

    async def fetch_articles(self, symbol: str, limit: int = 10) -> list[Any]:
        return []

    async def health_check(self) -> bool:
        return True

    @property
    def rate_limit(self) -> int:
        return 60


class DummySentimentAnalyzer:
    @property
    def name(self) -> str:
        return "dummy"

    async def score(self, text: str) -> Any:
        return {"score": 0.5}

    async def score_batch(self, texts: list[str]) -> list[Any]:
        return [{"score": 0.5} for _ in texts]


class DummyOnChainProvider:
    @property
    def name(self) -> str:
        return "dummy"

    async def get_metrics(self, symbol: str) -> dict[str, Any]:
        return {}

    async def health_check(self) -> bool:
        return True


class DummyFeatureProvider:
    @property
    def name(self) -> str:
        return "dummy"

    @property
    def required_inputs(self) -> list[str]:
        return ["price", "volume"]

    async def compute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {}


class DummyDataStore:
    async def initialize(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def save_trade(self, trade: TradeRecord) -> str:
        return trade.id

    async def list_trades(
        self, strategy: str | None = None, limit: int = 100
    ) -> list[TradeRecord]:
        return []

    async def save_signal(self, signal: SignalRecord) -> str:
        return signal.id

    async def list_signals(self, limit: int = 100) -> list[SignalRecord]:
        return []


# -- Non-conforming class (missing all methods) ------------------------------


class NonConforming:
    """A class that satisfies none of the protocols."""

    pass


# -- Tests --------------------------------------------------------------------


class TestHttpResponse:
    def test_status_code_and_text(self):
        resp = HttpResponse(200, '{"ok": true}')
        assert resp.status_code == 200
        assert resp.text == '{"ok": true}'

    def test_json_parsing(self):
        resp = HttpResponse(200, '{"key": "value"}')
        assert resp.json() == {"key": "value"}


class TestHttpClientProtocol:
    def test_conforming_class_is_instance(self):
        assert isinstance(DummyHttpClient(), HttpClient)

    def test_non_conforming_class_rejected(self):
        assert not isinstance(NonConforming(), HttpClient)


class TestMarketDataProviderProtocol:
    def test_conforming_class_is_instance(self):
        assert isinstance(DummyMarketDataProvider(), MarketDataProvider)

    def test_non_conforming_class_rejected(self):
        assert not isinstance(NonConforming(), MarketDataProvider)


class TestNewsProviderProtocol:
    def test_conforming_class_is_instance(self):
        assert isinstance(DummyNewsProvider(), NewsProvider)

    def test_non_conforming_class_rejected(self):
        assert not isinstance(NonConforming(), NewsProvider)


class TestSentimentAnalyzerProtocol:
    def test_conforming_class_is_instance(self):
        assert isinstance(DummySentimentAnalyzer(), SentimentAnalyzer)

    def test_non_conforming_class_rejected(self):
        assert not isinstance(NonConforming(), SentimentAnalyzer)


class TestOnChainProviderProtocol:
    def test_conforming_class_is_instance(self):
        assert isinstance(DummyOnChainProvider(), OnChainProvider)

    def test_non_conforming_class_rejected(self):
        assert not isinstance(NonConforming(), OnChainProvider)


class TestFeatureProviderProtocol:
    def test_conforming_class_is_instance(self):
        assert isinstance(DummyFeatureProvider(), FeatureProvider)

    def test_non_conforming_class_rejected(self):
        assert not isinstance(NonConforming(), FeatureProvider)


class TestDataStoreProtocol:
    def test_conforming_class_is_instance(self):
        assert isinstance(DummyDataStore(), DataStore)

    def test_non_conforming_class_rejected(self):
        assert not isinstance(NonConforming(), DataStore)
