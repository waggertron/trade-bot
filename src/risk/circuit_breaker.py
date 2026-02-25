"""Drawdown-based circuit breaker for risk management."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from src.core.event_bus import EventBus
from src.core.event_types import CircuitBreakerEvent


class DrawdownCircuitBreaker:
    """Trips when portfolio drawdown from peak exceeds a threshold.

    Once tripped, the breaker enters a cooldown period during which all
    trading is halted.  After cooldown expires the peak is reset to the
    current portfolio value and trading may resume.
    """

    def __init__(
        self,
        max_drawdown_pct: float = 10.0,
        cooldown_hours: float = 24.0,
    ) -> None:
        self._max_drawdown: float = max_drawdown_pct / 100.0
        self._cooldown: timedelta = timedelta(hours=cooldown_hours)
        self._peak_value: Decimal = Decimal("0")
        self._tripped_at: datetime | None = None
        self._event_bus: EventBus | None = None

    def set_event_bus(self, event_bus: EventBus) -> None:
        """Attach an event bus for publishing circuit breaker events."""
        self._event_bus = event_bus

    # -- mutators -------------------------------------------------------------

    def update(self, portfolio_value: Decimal, now: datetime) -> None:
        """Track peak portfolio value (high-water mark)."""
        self._peak_value = max(self._peak_value, portfolio_value)

    def reset(self) -> None:
        """Manual reset: clear peak and tripped state."""
        self._peak_value = Decimal("0")
        self._tripped_at = None

    # -- queries --------------------------------------------------------------

    def is_tripped(self, portfolio_value: Decimal, now: datetime) -> bool:
        """Return *True* if trading should be halted.

        The breaker trips when ``(peak - current) / peak`` reaches
        *max_drawdown_pct*.  Once tripped it stays tripped for the
        configured cooldown period.
        """
        # --- already in cooldown? ---
        if self._tripped_at is not None:
            if now - self._tripped_at < self._cooldown:
                return True
            # cooldown expired -> reset and allow trading
            self._tripped_at = None
            self._peak_value = portfolio_value
            return False

        # --- never seen a value yet ---
        if self._peak_value == 0:
            return False

        # --- check drawdown ---
        drawdown = float((self._peak_value - portfolio_value) / self._peak_value)
        if drawdown >= self._max_drawdown:
            self._tripped_at = now
            self._publish_tripped(drawdown * 100, portfolio_value)
            return True

        return False

    def _publish_tripped(self, drawdown_pct: float, current_value: Decimal) -> None:
        """Fire-and-forget event publish when the breaker trips."""
        if self._event_bus is None:
            return
        event = CircuitBreakerEvent(
            drawdown_pct=drawdown_pct,
            peak_value=self._peak_value,
            current_value=current_value,
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._event_bus.publish(event))
        except RuntimeError:
            # No running loop — skip event publishing
            pass

    # -- properties -----------------------------------------------------------

    @property
    def peak_value(self) -> Decimal:
        """Current high-water mark."""
        return self._peak_value

    @property
    def is_in_cooldown(self) -> bool:
        """Whether the breaker is currently in cooldown."""
        return self._tripped_at is not None
