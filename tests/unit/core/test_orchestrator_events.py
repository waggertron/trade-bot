"""Tests that orchestrator publishes typed events with payload data."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.core.event_bus import EventBus
from src.core.event_types import FillEvent
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


@pytest.fixture
def event_bus():
    bus = EventBus()
    bus.enable_history()
    return bus


@pytest.fixture
def mock_portfolio():
    portfolio = AsyncMock()
    portfolio.get_snapshot.return_value = PortfolioSnapshot(
        cash=Decimal("100000"),
        positions=[],
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    portfolio.record_fill.return_value = None
    return portfolio


@pytest.fixture
def mock_risk_manager():
    rm = AsyncMock()
    rm.evaluate_trade.return_value = RiskDecision(
        action=RiskAction.APPROVE,
        reason="OK",
    )
    return rm


@pytest.fixture
def mock_executor():
    executor = AsyncMock()
    executor.submit_order.return_value = Fill(
        order_id="order-1",
        symbol="BTC/USD",
        side=OrderSide.BUY,
        quantity=Decimal("0.5"),
        fill_price=Decimal("50000"),
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    return executor


@pytest.fixture
def buy_signal():
    return Signal(
        symbol="BTC/USD",
        direction=SignalDirection.BUY,
        confidence=0.9,
        strategy_name="momentum",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        reasoning="breakout",
    )


@pytest.fixture
def buy_strategy(buy_signal):
    strategy = AsyncMock()
    strategy.name = "momentum"
    strategy.evaluate.return_value = buy_signal
    return strategy


class TestOrchestratorFillEvents:
    async def test_publishes_fill_event_with_payload(
        self, event_bus, mock_portfolio, mock_risk_manager, mock_executor, buy_strategy,
    ):
        orchestrator = Orchestrator(
            strategies=[buy_strategy],
            risk_manager=mock_risk_manager,
            executor=mock_executor,
            portfolio=mock_portfolio,
            event_bus=event_bus,
        )

        tick = MarketTick(
            symbol="BTC/USD",
            price=Decimal("50000"),
            volume=100,
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            asset_type=AssetType.CRYPTO,
        )

        fills = await orchestrator.process_tick(tick)

        assert len(fills) == 1
        fill_events = event_bus.get_history("fill")
        assert len(fill_events) == 1

        fill_event = fill_events[0]
        assert isinstance(fill_event, FillEvent)
        assert fill_event.fill is fills[0]
        assert fill_event.strategy == "consensus"
