"""Tests for persisting signals to the database via orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.core.event_bus import EventBus
from src.core.models import (
    AssetType,
    Fill,
    MarketTick,
    OrderSide,
    PortfolioSnapshot,
    RiskAction,
    RiskDecision,
    Signal,
    SignalDirection,
)
from src.core.orchestrator import Orchestrator
from src.db.database import Database


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


def _make_tick(symbol="BTC/USD", price="50000"):
    return MarketTick(
        symbol=symbol,
        price=Decimal(price),
        volume=1000,
        timestamp=datetime.now(timezone.utc),
        asset_type=AssetType.CRYPTO,
    )


def _make_signal(symbol="BTC/USD", direction=SignalDirection.BUY):
    return Signal(
        symbol=symbol,
        direction=direction,
        confidence=0.8,
        strategy_name="test_strategy",
        timestamp=datetime.now(timezone.utc),
        reasoning="test reason",
    )


@pytest.mark.asyncio
async def test_orchestrator_persists_signals_when_db_provided(db):
    """When a db is provided, signals from _gather_signals should be persisted."""
    signal = _make_signal()

    strategy = AsyncMock()
    strategy.evaluate = AsyncMock(return_value=signal)

    risk_manager = AsyncMock()
    risk_manager.evaluate_trade = AsyncMock(
        return_value=RiskDecision(action=RiskAction.APPROVE, reason="ok")
    )

    portfolio = AsyncMock()
    portfolio.get_snapshot = AsyncMock(
        return_value=PortfolioSnapshot(
            cash=Decimal("100000"),
            positions=[],
            timestamp=datetime.now(timezone.utc),
        )
    )
    portfolio.record_fill = AsyncMock()

    executor = AsyncMock()
    executor.submit_order = AsyncMock(
        return_value=Fill(
            order_id="o1",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("0.04"),
            fill_price=Decimal("50000"),
            timestamp=datetime.now(timezone.utc),
        )
    )

    orchestrator = Orchestrator(
        strategies=[strategy],
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=EventBus(),
        db=db,
    )

    tick = _make_tick()
    await orchestrator.process_tick(tick)

    signals = await db.list_signals()
    assert len(signals) == 1
    assert signals[0].symbol == "BTC/USD"
    assert signals[0].direction == "buy"
    assert signals[0].strategy == "test_strategy"


@pytest.mark.asyncio
async def test_orchestrator_works_without_db():
    """When db is None, orchestrator should still work normally."""
    signal = _make_signal()

    strategy = AsyncMock()
    strategy.evaluate = AsyncMock(return_value=signal)

    risk_manager = AsyncMock()
    risk_manager.evaluate_trade = AsyncMock(
        return_value=RiskDecision(action=RiskAction.APPROVE, reason="ok")
    )

    portfolio = AsyncMock()
    portfolio.get_snapshot = AsyncMock(
        return_value=PortfolioSnapshot(
            cash=Decimal("100000"),
            positions=[],
            timestamp=datetime.now(timezone.utc),
        )
    )
    portfolio.record_fill = AsyncMock()

    executor = AsyncMock()
    executor.submit_order = AsyncMock(
        return_value=Fill(
            order_id="o1",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("0.04"),
            fill_price=Decimal("50000"),
            timestamp=datetime.now(timezone.utc),
        )
    )

    orchestrator = Orchestrator(
        strategies=[strategy],
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=EventBus(),
    )

    tick = _make_tick()
    fills = await orchestrator.process_tick(tick)
    assert len(fills) == 1  # Should still trade normally
