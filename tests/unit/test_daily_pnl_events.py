"""Tests for DailyPnLTracker publishing events via event bus."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.event_bus import EventBus
from src.core.event_types import DailyPnLEvent


class TestDailyPnLPublishing:
    async def test_publish_daily_pnl_event(self):
        bus = EventBus()
        bus.enable_history()

        event = DailyPnLEvent(
            daily_pnl=Decimal("-500"),
            portfolio_value=Decimal("99500"),
            trade_count=3,
        )
        await bus.publish(event)

        events = bus.get_history("daily_pnl")
        assert len(events) == 1
        assert isinstance(events[0], DailyPnLEvent)
        assert events[0].daily_pnl == Decimal("-500")
        assert events[0].portfolio_value == Decimal("99500")
        assert events[0].trade_count == 3

    async def test_discord_handler_receives_pnl_event(self):
        from unittest.mock import AsyncMock

        from src.discord_bot.alerts import DiscordAlertHandler

        bus = EventBus()
        mock_send = AsyncMock()
        handler = DiscordAlertHandler(send_fn=mock_send)
        handler.subscribe(bus)

        event = DailyPnLEvent(
            daily_pnl=Decimal("1200.50"),
            portfolio_value=Decimal("101200"),
            trade_count=5,
        )
        await bus.publish(event)

        mock_send.assert_called_once()
        message = mock_send.call_args[0][0]
        assert "1200" in message or "1,200" in message
