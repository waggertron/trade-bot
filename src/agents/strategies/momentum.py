from __future__ import annotations

from datetime import UTC, datetime

from src.core.models import MarketTick, ResearchReport, Signal, SignalDirection


class MomentumStrategy:
    name = "momentum"

    def __init__(self, short_window: int = 14, long_window: int = 50):
        self._short_window = short_window
        self._long_window = long_window

    async def evaluate(
        self,
        symbol: str,
        market_data: list[MarketTick],
        research: list[ResearchReport] | None = None,
    ) -> Signal | None:
        if len(market_data) < self._long_window:
            return None

        prices = [float(t.price) for t in market_data]

        short_ma = sum(prices[-self._short_window :]) / self._short_window
        long_ma = sum(prices[-self._long_window :]) / self._long_window

        if short_ma == long_ma:
            return None

        if short_ma > long_ma:
            direction = SignalDirection.BUY
            spread = (short_ma - long_ma) / long_ma
        else:
            direction = SignalDirection.SELL
            spread = (long_ma - short_ma) / long_ma

        confidence = min(spread * 10, 1.0)  # Scale spread to 0-1

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            strategy_name=self.name,
            timestamp=datetime.now(UTC),
            reasoning=f"Short MA ({self._short_window}): {short_ma:.2f}, "
            f"Long MA ({self._long_window}): {long_ma:.2f}, "
            f"Spread: {spread:.4f}",
        )
