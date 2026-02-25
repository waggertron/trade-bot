"""Tests for Discord bot event-based alert system."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.core.event_bus import EventBus
from src.core.event_types import (
    CircuitBreakerEvent,
    DailyPnLEvent,
    FillEvent,
)
from src.core.models import Fill, OrderSide
from src.discord_bot.alerts import DiscordAlertHandler


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def mock_send():
    return AsyncMock()


@pytest.fixture
def handler(event_bus, mock_send):
    h = DiscordAlertHandler(send_fn=mock_send)
    h.subscribe(event_bus)
    return h


class TestDiscordAlertHandlerSubscription:
    async def test_subscribes_to_fill_events(self, handler, event_bus, mock_send):
        fill = Fill(
            order_id="o1",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("0.5"),
            fill_price=Decimal("50000"),
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        )
        event = FillEvent(fill=fill, strategy="momentum", reasoning="breakout signal")

        await event_bus.publish(event)

        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]
        assert "BUY" in message
        assert "BTC/USD" in message
        assert "50000" in message
        assert "momentum" in message

    async def test_subscribes_to_circuit_breaker_events(self, handler, event_bus, mock_send):
        event = CircuitBreakerEvent(
            drawdown_pct=12.5,
            peak_value=Decimal("100000"),
            current_value=Decimal("87500"),
        )

        await event_bus.publish(event)

        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]
        assert "circuit breaker" in message.lower() or "CIRCUIT BREAKER" in message
        assert "12.5" in message

    async def test_subscribes_to_daily_pnl_events(self, handler, event_bus, mock_send):
        event = DailyPnLEvent(
            daily_pnl=Decimal("-1500.50"),
            portfolio_value=Decimal("98500"),
            trade_count=7,
        )

        await event_bus.publish(event)

        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]
        assert "1500" in message or "1,500" in message
        assert "98500" in message or "98,500" in message

    async def test_fill_message_includes_sell_side(self, handler, event_bus, mock_send):
        fill = Fill(
            order_id="o2",
            symbol="ETH/USD",
            side=OrderSide.SELL,
            quantity=Decimal("10"),
            fill_price=Decimal("3000"),
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        )
        event = FillEvent(fill=fill, strategy="sentiment")

        await event_bus.publish(event)

        message = mock_send.call_args[0][0]
        assert "SELL" in message
        assert "ETH/USD" in message

    async def test_unsubscribe_stops_alerts(self, handler, event_bus, mock_send):
        handler.unsubscribe(event_bus)

        fill = Fill(
            order_id="o1",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            fill_price=Decimal("100"),
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        )
        await event_bus.publish(FillEvent(fill=fill, strategy="test"))

        mock_send.assert_not_called()

    async def test_positive_pnl_message(self, handler, event_bus, mock_send):
        event = DailyPnLEvent(
            daily_pnl=Decimal("2500.00"),
            portfolio_value=Decimal("102500"),
            trade_count=5,
        )

        await event_bus.publish(event)

        message = mock_send.call_args[0][0]
        assert "2500" in message or "2,500" in message
