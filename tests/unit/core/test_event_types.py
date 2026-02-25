"""Tests for typed event classes with payload data."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.event_bus import Event
from src.core.event_types import (
    CircuitBreakerEvent,
    DailyPnLEvent,
    FillEvent,
)
from src.core.models import Fill, OrderSide


class TestFillEvent:
    def test_carries_fill_and_strategy(self):
        fill = Fill(
            order_id="order-1",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("0.5"),
            fill_price=Decimal("50000"),
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        event = FillEvent(fill=fill, strategy="momentum", reasoning="breakout")

        assert event.event_type == "fill"
        assert event.fill is fill
        assert event.strategy == "momentum"
        assert event.reasoning == "breakout"

    def test_is_subclass_of_event(self):
        fill = Fill(
            order_id="order-1",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            fill_price=Decimal("100"),
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        event = FillEvent(fill=fill, strategy="test")
        assert isinstance(event, Event)


class TestCircuitBreakerEvent:
    def test_carries_drawdown_info(self):
        event = CircuitBreakerEvent(
            drawdown_pct=12.5,
            peak_value=Decimal("100000"),
            current_value=Decimal("87500"),
        )

        assert event.event_type == "circuit_breaker_tripped"
        assert event.drawdown_pct == 12.5
        assert event.peak_value == Decimal("100000")
        assert event.current_value == Decimal("87500")

    def test_is_subclass_of_event(self):
        event = CircuitBreakerEvent(
            drawdown_pct=10.0,
            peak_value=Decimal("100000"),
            current_value=Decimal("90000"),
        )
        assert isinstance(event, Event)


class TestDailyPnLEvent:
    def test_carries_pnl_summary(self):
        event = DailyPnLEvent(
            daily_pnl=Decimal("-1500.50"),
            portfolio_value=Decimal("98500"),
            trade_count=7,
        )

        assert event.event_type == "daily_pnl"
        assert event.daily_pnl == Decimal("-1500.50")
        assert event.portfolio_value == Decimal("98500")
        assert event.trade_count == 7

    def test_is_subclass_of_event(self):
        event = DailyPnLEvent(
            daily_pnl=Decimal("500"),
            portfolio_value=Decimal("100500"),
            trade_count=3,
        )
        assert isinstance(event, Event)
