"""Strategy adapters that implement FeatureStrategy using FeatureVector inputs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.core.models import Signal, SignalDirection

if TYPE_CHECKING:
    from src.ml.models import FeatureVector


class MomentumAdapter:
    """Feature-based momentum strategy comparing short and long SMAs."""

    name: str = "momentum"

    async def evaluate(
        self,
        symbol: str,
        features: FeatureVector,
    ) -> Signal | None:
        sma_5 = features.features.get("sma_5")
        sma_14 = features.features.get("sma_14")

        if sma_5 is None or sma_14 is None:
            return None
        if sma_14 == 0:
            return None
        if sma_5 == sma_14:
            return None

        spread = abs(sma_5 - sma_14) / sma_14
        confidence = min(spread * 10, 1.0)

        direction = SignalDirection.BUY if sma_5 > sma_14 else SignalDirection.SELL

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            strategy_name="momentum",
            reasoning=f"SMA5 ({sma_5:.2f}) > SMA14 ({sma_14:.2f})"
            if direction == SignalDirection.BUY
            else f"SMA5 ({sma_5:.2f}) < SMA14 ({sma_14:.2f})",
            timestamp=datetime.now(UTC),
        )

    def required_features(self) -> list[str]:
        return ["sma_5", "sma_14"]


class SentimentAdapter:
    """Feature-based sentiment strategy using aggregated sentiment scores."""

    name: str = "sentiment"

    def __init__(
        self,
        buy_threshold: float = 0.6,
        sell_threshold: float = -0.6,
    ) -> None:
        self._buy_threshold = buy_threshold
        self._sell_threshold = sell_threshold

    async def evaluate(
        self,
        symbol: str,
        features: FeatureVector,
    ) -> Signal | None:
        sentiment = features.features.get("sentiment_avg_6h")

        if sentiment is None:
            return None

        if sentiment >= self._buy_threshold:
            direction = SignalDirection.BUY
        elif sentiment <= self._sell_threshold:
            direction = SignalDirection.SELL
        else:
            return None

        confidence = min(abs(sentiment), 1.0)

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            strategy_name="sentiment",
            reasoning=f"Sentiment ({sentiment:.2f}) triggered {direction.value}",
            timestamp=datetime.now(UTC),
        )

    def required_features(self) -> list[str]:
        return ["sentiment_avg_6h"]


class QuantitativeAdapter:
    """Feature-based mean-reversion strategy using price z-scores."""

    name: str = "quantitative"

    def __init__(self, z_threshold: float = 2.0) -> None:
        self._z_threshold = z_threshold

    async def evaluate(
        self,
        symbol: str,
        features: FeatureVector,
    ) -> Signal | None:
        zscore = features.features.get("price_zscore")

        if zscore is None:
            return None

        if zscore <= -self._z_threshold:
            direction = SignalDirection.BUY
        elif zscore >= self._z_threshold:
            direction = SignalDirection.SELL
        else:
            return None

        confidence = min(abs(zscore) / (self._z_threshold * 2), 1.0)

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            strategy_name="quantitative",
            reasoning=f"Z-score ({zscore:.2f}) triggered {direction.value}",
            timestamp=datetime.now(UTC),
        )

    def required_features(self) -> list[str]:
        return ["price_zscore"]
