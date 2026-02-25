"""Event-driven alert handler for Discord notifications."""

from __future__ import annotations

from typing import Any, Callable, Coroutine

from src.core.event_bus import Event, EventBus
from src.core.event_types import CircuitBreakerEvent, DailyPnLEvent, FillEvent
from src.discord_bot.bot import format_trade_alert


class DiscordAlertHandler:
    """Subscribes to event bus and sends formatted Discord alerts."""

    def __init__(self, send_fn: Callable[[str], Coroutine[Any, Any, None]]) -> None:
        self._send_fn = send_fn

    def subscribe(self, event_bus: EventBus) -> None:
        event_bus.subscribe("fill", self._on_fill)
        event_bus.subscribe("circuit_breaker_tripped", self._on_circuit_breaker)
        event_bus.subscribe("daily_pnl", self._on_daily_pnl)

    def unsubscribe(self, event_bus: EventBus) -> None:
        event_bus.unsubscribe("fill", self._on_fill)
        event_bus.unsubscribe("circuit_breaker_tripped", self._on_circuit_breaker)
        event_bus.unsubscribe("daily_pnl", self._on_daily_pnl)

    async def _on_fill(self, event: Event) -> None:
        if not isinstance(event, FillEvent) or event.fill is None:
            return
        message = format_trade_alert(
            event.fill,
            strategy=event.strategy,
            reasoning=event.reasoning,
        )
        await self._send_fn(message)

    async def _on_circuit_breaker(self, event: Event) -> None:
        if not isinstance(event, CircuitBreakerEvent):
            return
        message = (
            f"**CIRCUIT BREAKER TRIPPED**\n"
            f"Drawdown: {event.drawdown_pct:.1f}%\n"
            f"Peak: ${event.peak_value:,.2f}\n"
            f"Current: ${event.current_value:,.2f}"
        )
        await self._send_fn(message)

    async def _on_daily_pnl(self, event: Event) -> None:
        if not isinstance(event, DailyPnLEvent):
            return
        pnl = event.daily_pnl
        sign = "+" if pnl >= 0 else ""
        message = (
            f"**Daily P&L Summary**\n"
            f"P&L: {sign}${pnl:,.2f}\n"
            f"Portfolio Value: ${event.portfolio_value:,.2f}\n"
            f"Trades: {event.trade_count}"
        )
        await self._send_fn(message)
