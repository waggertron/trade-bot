"""Tests for wiring PositionSizer into Orchestrator."""

from __future__ import annotations

from datetime import UTC, datetime
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
from src.risk.fixed_sizer import FixedPositionSizer


def _make_tick(symbol="BTC/USD", price="50000"):
    return MarketTick(
        symbol=symbol,
        price=Decimal(price),
        volume=1000,
        timestamp=datetime.now(UTC),
        asset_type=AssetType.CRYPTO,
    )


def _make_signal(symbol="BTC/USD", direction=SignalDirection.BUY):
    return Signal(
        symbol=symbol,
        direction=direction,
        confidence=0.8,
        strategy_name="test",
        timestamp=datetime.now(UTC),
        reasoning="test",
    )


def _make_portfolio(cash="100000"):
    return PortfolioSnapshot(
        cash=Decimal(cash),
        positions=[],
        timestamp=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_position_sizer_delegates_compute_quantity():
    """When a PositionSizer is provided, _compute_quantity should delegate to it."""
    sizer = FixedPositionSizer(position_pct=5.0)

    signal = _make_signal()
    strategy = AsyncMock()
    strategy.evaluate = AsyncMock(return_value=signal)

    risk_manager = AsyncMock()
    risk_manager.evaluate_trade = AsyncMock(
        return_value=RiskDecision(action=RiskAction.APPROVE, reason="ok")
    )

    portfolio = AsyncMock()
    portfolio.get_snapshot = AsyncMock(return_value=_make_portfolio())
    portfolio.record_fill = AsyncMock()

    executor = AsyncMock()
    fill = Fill(
        order_id="o1",
        symbol="BTC/USD",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        fill_price=Decimal("50000"),
        timestamp=datetime.now(UTC),
    )
    executor.submit_order = AsyncMock(return_value=fill)

    orchestrator = Orchestrator(
        strategies=[strategy],
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=EventBus(),
        position_sizer=sizer,
    )

    tick = _make_tick()
    fills = await orchestrator.process_tick(tick)
    assert len(fills) == 1

    # The order should have been submitted. Check the quantity:
    # 5% of $100,000 = $5,000; $5,000 / $50,000 per BTC = 0.1 BTC
    order_arg = executor.submit_order.call_args[0][0]
    assert order_arg.quantity == Decimal("5000") / Decimal("50000")


@pytest.mark.asyncio
async def test_without_position_sizer_uses_default():
    """Without a PositionSizer, the default 2% hardcoded sizing is used."""
    signal = _make_signal()
    strategy = AsyncMock()
    strategy.evaluate = AsyncMock(return_value=signal)

    risk_manager = AsyncMock()
    risk_manager.evaluate_trade = AsyncMock(
        return_value=RiskDecision(action=RiskAction.APPROVE, reason="ok")
    )

    portfolio = AsyncMock()
    portfolio.get_snapshot = AsyncMock(return_value=_make_portfolio())
    portfolio.record_fill = AsyncMock()

    executor = AsyncMock()
    fill = Fill(
        order_id="o1",
        symbol="BTC/USD",
        side=OrderSide.BUY,
        quantity=Decimal("0.04"),
        fill_price=Decimal("50000"),
        timestamp=datetime.now(UTC),
    )
    executor.submit_order = AsyncMock(return_value=fill)

    orchestrator = Orchestrator(
        strategies=[strategy],
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=EventBus(),
    )

    tick = _make_tick()
    fills = await orchestrator.process_tick(tick)
    assert len(fills) == 1

    # Default 2% of $100,000 = $2,000; $2,000 / $50,000 = 0.04
    order_arg = executor.submit_order.call_args[0][0]
    assert order_arg.quantity == Decimal("2000") / Decimal("50000")


def test_build_position_sizer_mock_true():
    """When use_mocks.position_sizer=True, FixedPositionSizer is returned."""
    from main import build_position_sizer
    from src.core.config import Settings

    settings = Settings.for_testing(use_mocks={"position_sizer": True})
    sizer = build_position_sizer(settings)
    assert isinstance(sizer, FixedPositionSizer)


def test_build_position_sizer_mock_false():
    """When use_mocks.position_sizer=False, VolTargetedPositionSizer is returned."""
    from main import build_position_sizer
    from src.core.config import Settings
    from src.risk.vol_sizer import VolTargetedPositionSizer

    settings = Settings.for_testing(use_mocks={"position_sizer": False})
    sizer = build_position_sizer(settings)
    assert isinstance(sizer, VolTargetedPositionSizer)
