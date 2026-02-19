"""Tests for publishing trading events to the event bus."""

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
        strategy_name="test",
        timestamp=datetime.now(timezone.utc),
        reasoning="test",
    )


@pytest.mark.asyncio
async def test_process_tick_publishes_signal_event():
    """process_tick should publish a 'signal' event when signals are generated."""
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

    event_bus = EventBus()
    event_bus.enable_history()

    orchestrator = Orchestrator(
        strategies=[strategy],
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=event_bus,
    )

    tick = _make_tick()
    await orchestrator.process_tick(tick)

    signal_events = event_bus.get_history("signal")
    assert len(signal_events) >= 1


@pytest.mark.asyncio
async def test_process_tick_publishes_risk_decision_event():
    """process_tick should publish a 'risk_decision' event."""
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

    event_bus = EventBus()
    event_bus.enable_history()

    orchestrator = Orchestrator(
        strategies=[strategy],
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=event_bus,
    )

    tick = _make_tick()
    await orchestrator.process_tick(tick)

    risk_events = event_bus.get_history("risk_decision")
    assert len(risk_events) >= 1


@pytest.mark.asyncio
async def test_process_tick_publishes_fill_event():
    """process_tick should publish a 'fill' event after a trade executes."""
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

    event_bus = EventBus()
    event_bus.enable_history()

    orchestrator = Orchestrator(
        strategies=[strategy],
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=event_bus,
    )

    tick = _make_tick()
    await orchestrator.process_tick(tick)

    fill_events = event_bus.get_history("fill")
    assert len(fill_events) == 1


@pytest.mark.asyncio
async def test_veto_publishes_risk_decision_but_no_fill():
    """When risk vetoes, risk_decision event is published but no fill event."""
    signal = _make_signal()
    strategy = AsyncMock()
    strategy.evaluate = AsyncMock(return_value=signal)

    risk_manager = AsyncMock()
    risk_manager.evaluate_trade = AsyncMock(
        return_value=RiskDecision(action=RiskAction.VETO, reason="too risky")
    )

    portfolio = AsyncMock()
    portfolio.get_snapshot = AsyncMock(
        return_value=PortfolioSnapshot(
            cash=Decimal("100000"),
            positions=[],
            timestamp=datetime.now(timezone.utc),
        )
    )

    event_bus = EventBus()
    event_bus.enable_history()

    orchestrator = Orchestrator(
        strategies=[strategy],
        risk_manager=risk_manager,
        executor=AsyncMock(),
        portfolio=portfolio,
        event_bus=event_bus,
    )

    tick = _make_tick()
    await orchestrator.process_tick(tick)

    risk_events = event_bus.get_history("risk_decision")
    assert len(risk_events) >= 1
    fill_events = event_bus.get_history("fill")
    assert len(fill_events) == 0
