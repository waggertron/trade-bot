"""Typed event classes for the event bus with payload data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from src.core.event_bus import Event
from src.core.models import Fill


@dataclass
class FillEvent(Event):
    """Published when an order is filled."""

    event_type: str = field(default="fill", init=False)
    fill: Fill | None = None
    strategy: str = ""
    reasoning: str = ""


@dataclass
class CircuitBreakerEvent(Event):
    """Published when the circuit breaker trips."""

    event_type: str = field(default="circuit_breaker_tripped", init=False)
    drawdown_pct: float = 0.0
    peak_value: Decimal = Decimal("0")
    current_value: Decimal = Decimal("0")


@dataclass
class DailyPnLEvent(Event):
    """Published at end of day with P&L summary."""

    event_type: str = field(default="daily_pnl", init=False)
    daily_pnl: Decimal = Decimal("0")
    portfolio_value: Decimal = Decimal("0")
    trade_count: int = 0
