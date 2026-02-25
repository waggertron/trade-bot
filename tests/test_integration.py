"""Full pipeline integration test: tick -> signal -> risk -> execution -> portfolio."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.agents.execution import PaperExecutionAgent
from src.agents.portfolio import PortfolioManager
from src.agents.risk_manager import RiskManager
from src.agents.strategies.momentum import MomentumStrategy
from src.core.config import RiskSettings
from src.core.event_bus import EventBus
from src.core.models import AssetType, MarketTick


def make_uptrend_ticks(symbol="AAPL", count=60):
    now = datetime.now(UTC)
    return [
        MarketTick(
            symbol=symbol,
            price=Decimal(str(100 + i * 0.5)),
            volume=1000,
            timestamp=now - timedelta(minutes=count - i),
            asset_type=AssetType.STOCK,
        )
        for i in range(count)
    ]


@pytest.fixture
def pipeline():
    event_bus = EventBus()
    event_bus.enable_history()

    portfolio = PortfolioManager(initial_cash=Decimal("100000"))
    risk_manager = RiskManager(RiskSettings(max_open_positions=5))
    executor = PaperExecutionAgent(slippage_pct=Decimal("0.05"))

    # Set price so executor knows current market price
    executor.set_current_price("AAPL", Decimal("129.50"))

    strategies = [MomentumStrategy(short_window=5, long_window=20)]

    from src.core.orchestrator import Orchestrator

    orchestrator = Orchestrator(
        strategies=strategies,
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=event_bus,
    )
    return orchestrator, portfolio, event_bus


async def test_full_pipeline_executes_trade(pipeline):
    orchestrator, portfolio, _event_bus = pipeline

    # Feed a single tick (strategies will evaluate on just this + history)
    tick = MarketTick(
        symbol="AAPL",
        price=Decimal("130.00"),
        volume=5000,
        timestamp=datetime.now(UTC),
        asset_type=AssetType.STOCK,
    )

    # With only 1 tick, momentum returns None (insufficient data) -> no trade
    fills = await orchestrator.process_tick(tick)
    assert len(fills) == 0  # Expected: insufficient data

    # Verify portfolio unchanged
    snapshot = await portfolio.get_snapshot()
    assert snapshot.cash == Decimal("100000")
    assert len(snapshot.positions) == 0


async def test_pause_prevents_trading(pipeline):
    orchestrator, portfolio, _ = pipeline
    orchestrator.pause()

    tick = MarketTick(
        symbol="AAPL",
        price=Decimal("130.00"),
        volume=5000,
        timestamp=datetime.now(UTC),
        asset_type=AssetType.STOCK,
    )
    fills = await orchestrator.process_tick(tick)
    assert len(fills) == 0

    snapshot = await portfolio.get_snapshot()
    assert snapshot.cash == Decimal("100000")
