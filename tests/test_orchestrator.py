from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.core.event_bus import EventBus
from src.core.models import (
    AssetType,
    Fill,
    MarketTick,
    OrderSide,
    PortfolioSnapshot,
    ResearchReport,
    RiskAction,
    RiskDecision,
    Signal,
    SignalDirection,
)
from src.core.orchestrator import Orchestrator


class MockStrategy:
    def __init__(self, name, direction=SignalDirection.BUY, confidence=0.8):
        self.name = name
        self._direction = direction
        self._confidence = confidence

    async def evaluate(self, symbol, market_data, research=None):
        return Signal(
            symbol=symbol,
            direction=self._direction,
            confidence=self._confidence,
            strategy_name=self.name,
            timestamp=datetime.now(UTC),
            reasoning=f"{self.name} signal",
        )


class MockRiskManager:
    def __init__(self, approve=True):
        self._approve = approve

    async def evaluate_trade(self, signal, portfolio):
        if self._approve:
            return RiskDecision(action=RiskAction.APPROVE, reason="approved")
        return RiskDecision(action=RiskAction.VETO, reason="vetoed")

    async def check_portfolio_health(self, portfolio):
        return []


class MockExecutor:
    def __init__(self):
        self.submitted_orders = []

    async def submit_order(self, order):
        self.submitted_orders.append(order)
        return Fill(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=Decimal("150"),
            timestamp=datetime.now(UTC),
        )

    async def cancel_order(self, order_id):
        return True

    async def cancel_all(self):
        return 0


class MockPortfolio:
    async def get_snapshot(self):
        return PortfolioSnapshot(
            cash=Decimal("100000"),
            positions=[],
            timestamp=datetime.now(UTC),
        )

    async def record_fill(self, fill):
        pass

    async def get_positions(self):
        return []

    async def get_pnl(self, period):
        return 0.0


@pytest.fixture
def bus():
    return EventBus()


async def test_process_signals_executes_trade(bus):
    strategies = [MockStrategy("momentum"), MockStrategy("sentiment")]
    orchestrator = Orchestrator(
        strategies=strategies,
        risk_manager=MockRiskManager(approve=True),
        executor=MockExecutor(),
        portfolio=MockPortfolio(),
        event_bus=bus,
    )
    tick = MarketTick(
        symbol="AAPL",
        price=Decimal("150"),
        volume=1000,
        timestamp=datetime.now(UTC),
        asset_type=AssetType.STOCK,
    )
    fills = await orchestrator.process_tick(tick)
    assert len(fills) == 1  # Agreeing signals = one trade


async def test_risk_veto_prevents_trade(bus):
    strategies = [MockStrategy("momentum")]
    orchestrator = Orchestrator(
        strategies=strategies,
        risk_manager=MockRiskManager(approve=False),
        executor=MockExecutor(),
        portfolio=MockPortfolio(),
        event_bus=bus,
    )
    tick = MarketTick(
        symbol="AAPL",
        price=Decimal("150"),
        volume=1000,
        timestamp=datetime.now(UTC),
        asset_type=AssetType.STOCK,
    )
    fills = await orchestrator.process_tick(tick)
    assert len(fills) == 0


async def test_conflicting_signals_tie_break_by_confidence(bus):
    strategies = [
        MockStrategy("momentum", direction=SignalDirection.BUY, confidence=0.9),
        MockStrategy("sentiment", direction=SignalDirection.SELL, confidence=0.6),
    ]
    orchestrator = Orchestrator(
        strategies=strategies,
        risk_manager=MockRiskManager(approve=True),
        executor=MockExecutor(),
        portfolio=MockPortfolio(),
        event_bus=bus,
    )
    tick = MarketTick(
        symbol="AAPL",
        price=Decimal("150"),
        volume=1000,
        timestamp=datetime.now(UTC),
        asset_type=AssetType.STOCK,
    )
    fills = await orchestrator.process_tick(tick)
    # Conflicting signals resolved by highest confidence (BUY @ 0.9)
    assert len(fills) == 1
    assert fills[0].side == OrderSide.BUY


async def test_pause_and_resume(bus):
    strategies = [MockStrategy("momentum")]
    executor = MockExecutor()
    orchestrator = Orchestrator(
        strategies=strategies,
        risk_manager=MockRiskManager(approve=True),
        executor=executor,
        portfolio=MockPortfolio(),
        event_bus=bus,
    )
    orchestrator.pause()
    tick = MarketTick(
        symbol="AAPL",
        price=Decimal("150"),
        volume=1000,
        timestamp=datetime.now(UTC),
        asset_type=AssetType.STOCK,
    )
    fills = await orchestrator.process_tick(tick)
    assert len(fills) == 0
    assert len(executor.submitted_orders) == 0

    orchestrator.resume()
    fills = await orchestrator.process_tick(tick)
    assert len(fills) == 1


class ResearchCapturingStrategy:
    """Strategy that captures the research reports it receives."""

    name = "research_capturer"

    def __init__(self):
        self.received_research = None

    async def evaluate(self, symbol, market_data, research=None):
        self.received_research = research
        return Signal(
            symbol=symbol,
            direction=SignalDirection.BUY,
            confidence=0.7,
            strategy_name=self.name,
            timestamp=datetime.now(UTC),
            reasoning="test",
        )


async def test_set_research_passes_reports_to_strategies(bus):
    """Orchestrator passes stored research reports to strategy.evaluate()."""
    strategy = ResearchCapturingStrategy()
    orchestrator = Orchestrator(
        strategies=[strategy],
        risk_manager=MockRiskManager(approve=True),
        executor=MockExecutor(),
        portfolio=MockPortfolio(),
        event_bus=bus,
    )

    reports = [
        ResearchReport(
            symbol="AAPL",
            summary="Bullish sentiment from news",
            sentiment_score=0.8,
            timestamp=datetime.now(UTC),
            sources=["sentiment_pipeline"],
        ),
    ]
    orchestrator.set_research(reports)

    tick = MarketTick(
        symbol="AAPL",
        price=Decimal("150"),
        volume=1000,
        timestamp=datetime.now(UTC),
        asset_type=AssetType.STOCK,
    )
    await orchestrator.process_tick(tick)

    assert strategy.received_research is not None
    assert len(strategy.received_research) == 1
    assert strategy.received_research[0].sentiment_score == 0.8


async def test_research_defaults_to_empty_when_not_set(bus):
    """Without set_research, strategies receive None for research."""
    strategy = ResearchCapturingStrategy()
    orchestrator = Orchestrator(
        strategies=[strategy],
        risk_manager=MockRiskManager(approve=True),
        executor=MockExecutor(),
        portfolio=MockPortfolio(),
        event_bus=bus,
    )

    tick = MarketTick(
        symbol="AAPL",
        price=Decimal("150"),
        volume=1000,
        timestamp=datetime.now(UTC),
        asset_type=AssetType.STOCK,
    )
    await orchestrator.process_tick(tick)

    assert strategy.received_research is None
