"""Tests that circuit breaker publishes events when tripping."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.core.event_bus import EventBus
from src.core.event_types import CircuitBreakerEvent
from src.risk.circuit_breaker import DrawdownCircuitBreaker


class TestCircuitBreakerEvents:
    async def test_publishes_event_when_tripped(self):
        bus = EventBus()
        bus.enable_history()

        cb = DrawdownCircuitBreaker(max_drawdown_pct=10.0, cooldown_hours=24.0)
        cb.set_event_bus(bus)

        now = datetime(2024, 1, 1, tzinfo=UTC)
        # Set peak
        cb.update(Decimal("100000"), now)
        # Trigger drawdown
        cb.is_tripped(Decimal("89000"), now)

        # Yield to let fire-and-forget task complete
        await asyncio.sleep(0)

        events = bus.get_history("circuit_breaker_tripped")
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, CircuitBreakerEvent)
        assert event.drawdown_pct == pytest.approx(11.0, abs=0.1)
        assert event.peak_value == Decimal("100000")
        assert event.current_value == Decimal("89000")

    async def test_no_event_when_not_tripped(self):
        bus = EventBus()
        bus.enable_history()

        cb = DrawdownCircuitBreaker(max_drawdown_pct=10.0, cooldown_hours=24.0)
        cb.set_event_bus(bus)

        now = datetime(2024, 1, 1, tzinfo=UTC)
        cb.update(Decimal("100000"), now)
        cb.is_tripped(Decimal("95000"), now)  # only 5% drawdown

        await asyncio.sleep(0)

        events = bus.get_history("circuit_breaker_tripped")
        assert len(events) == 0

    async def test_works_without_event_bus(self):
        """Circuit breaker still works when no event bus is set."""
        cb = DrawdownCircuitBreaker(max_drawdown_pct=10.0, cooldown_hours=24.0)

        now = datetime(2024, 1, 1, tzinfo=UTC)
        cb.update(Decimal("100000"), now)
        assert cb.is_tripped(Decimal("89000"), now) is True
