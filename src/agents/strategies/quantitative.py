from __future__ import annotations

import math
from datetime import datetime, timezone

from src.core.models import MarketTick, ResearchReport, Signal, SignalDirection


class QuantitativeStrategy:
    name = "quantitative"

    def __init__(self, lookback: int = 20, z_threshold: float = 2.0):
        self._lookback = lookback
        self._z_threshold = z_threshold

    async def evaluate(
        self,
        symbol: str,
        market_data: list[MarketTick],
        research: list[ResearchReport] | None = None,
    ) -> Signal | None:
        if len(market_data) < self._lookback + 1:
            return None

        prices = [float(t.price) for t in market_data]
        lookback_prices = prices[-(self._lookback + 1):-1]
        current_price = prices[-1]

        mean = sum(lookback_prices) / len(lookback_prices)
        variance = sum((p - mean) ** 2 for p in lookback_prices) / len(lookback_prices)
        std = math.sqrt(variance) if variance > 0 else 0.0

        if std == 0:
            return None

        z_score = (current_price - mean) / std

        if z_score <= -self._z_threshold:
            direction = SignalDirection.BUY
            confidence = min(abs(z_score) / (self._z_threshold * 2), 1.0)
            reasoning = f"Mean reversion BUY: z-score={z_score:.2f}, mean={mean:.2f}, std={std:.2f}"
        elif z_score >= self._z_threshold:
            direction = SignalDirection.SELL
            confidence = min(abs(z_score) / (self._z_threshold * 2), 1.0)
            reasoning = f"Mean reversion SELL: z-score={z_score:.2f}, mean={mean:.2f}, std={std:.2f}"
        else:
            return None

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            strategy_name=self.name,
            timestamp=datetime.now(timezone.utc),
            reasoning=reasoning,
        )
