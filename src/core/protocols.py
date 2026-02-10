from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from src.core.models import (
    Fill, MarketTick, Order, PortfolioSnapshot, Position,
    ResearchReport, RiskDecision, Signal,
)


@runtime_checkable
class MarketDataAgent(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def stream_ticks(self, symbols: list[str]) -> AsyncIterator[MarketTick]: ...
    async def get_order_book(self, symbol: str) -> dict: ...


@runtime_checkable
class ResearchAgent(Protocol):
    async def run_research(self, symbols: list[str]) -> list[ResearchReport]: ...
    async def score_headline(self, headline: str) -> float: ...


@runtime_checkable
class StrategyAgent(Protocol):
    name: str
    async def evaluate(
        self,
        symbol: str,
        market_data: list[MarketTick],
        research: list[ResearchReport] | None = None,
    ) -> Signal | None: ...


@runtime_checkable
class RiskManagerAgent(Protocol):
    async def evaluate_trade(
        self, signal: Signal, portfolio: PortfolioSnapshot,
    ) -> RiskDecision: ...
    async def check_portfolio_health(
        self, portfolio: PortfolioSnapshot,
    ) -> list[str]: ...


@runtime_checkable
class ExecutionAgent(Protocol):
    async def submit_order(self, order: Order) -> Fill: ...
    async def cancel_order(self, order_id: str) -> bool: ...
    async def cancel_all(self) -> int: ...


@runtime_checkable
class PortfolioAgent(Protocol):
    async def get_snapshot(self) -> PortfolioSnapshot: ...
    async def record_fill(self, fill: Fill) -> None: ...
    async def get_positions(self) -> list[Position]: ...
    async def get_pnl(self, period: str) -> float: ...
