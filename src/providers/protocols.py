"""Provider protocols for all subsystem interfaces.

These protocols define the contracts that providers must satisfy.
Using @runtime_checkable allows isinstance() checks at runtime.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from src.core.models import MarketTick
from src.db.models import SignalRecord, TradeRecord


# -- Concrete helper classes --------------------------------------------------


class HttpResponse:
    """Concrete class representing an HTTP response."""

    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text

    def json(self) -> Any:
        """Parse response text as JSON."""
        import json

        return json.loads(self.text)


# -- Protocols ----------------------------------------------------------------


@runtime_checkable
class HttpClient(Protocol):
    """Protocol for making HTTP requests."""

    async def get(self, url: str, **kwargs: Any) -> HttpResponse: ...

    async def post(self, url: str, **kwargs: Any) -> HttpResponse: ...

    async def close(self) -> None: ...


@runtime_checkable
class MarketDataProvider(Protocol):
    """Protocol for fetching market data (ticks, OHLC bars)."""

    @property
    def name(self) -> str: ...

    async def get_ticks(self, symbols: list[str]) -> list[MarketTick]: ...

    async def get_ohlc(
        self,
        symbol: str,
        interval: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...

    async def health_check(self) -> bool: ...


@runtime_checkable
class NewsProvider(Protocol):
    """Protocol for fetching news articles."""

    @property
    def name(self) -> str: ...

    async def fetch_articles(
        self,
        symbol: str,
        limit: int = 10,
    ) -> list[Any]: ...

    async def health_check(self) -> bool: ...

    @property
    def rate_limit(self) -> int: ...


@runtime_checkable
class SentimentAnalyzer(Protocol):
    """Protocol for analysing sentiment of text."""

    @property
    def name(self) -> str: ...

    async def score(self, text: str) -> Any:
        """Score a single piece of text. Returns a SentimentResult."""
        ...

    async def score_batch(self, texts: list[str]) -> list[Any]:
        """Score multiple texts. Returns a list of SentimentResult."""
        ...


@runtime_checkable
class OnChainProvider(Protocol):
    """Protocol for fetching on-chain metrics."""

    @property
    def name(self) -> str: ...

    async def get_metrics(self, symbol: str) -> dict[str, Any]: ...

    async def health_check(self) -> bool: ...


@runtime_checkable
class FeatureProvider(Protocol):
    """Protocol for computing derived features for ML / strategy use."""

    @property
    def name(self) -> str: ...

    @property
    def required_inputs(self) -> list[str]: ...

    async def compute(self, inputs: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class DataStore(Protocol):
    """Protocol for persistent data storage."""

    async def initialize(self) -> None: ...

    async def close(self) -> None: ...

    async def save_trade(self, trade: TradeRecord) -> str: ...

    async def list_trades(
        self,
        strategy: str | None = None,
        limit: int = 100,
    ) -> list[TradeRecord]: ...

    async def save_signal(self, signal: SignalRecord) -> str: ...

    async def list_signals(self, limit: int = 100) -> list[SignalRecord]: ...
