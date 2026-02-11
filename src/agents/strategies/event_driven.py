"""Event-driven strategy that reacts to news volume spikes and sentiment shifts."""

from __future__ import annotations

from datetime import datetime, timezone

from src.core.models import Signal, SignalDirection
from src.ml.models import FeatureVector


class EventDrivenStrategy:
    """Strategy that generates signals based on article volume spikes and sentiment."""

    name: str = "event_driven"

    def __init__(
        self,
        volume_spike_threshold: float = 3.0,
        sentiment_threshold: float = 0.5,
    ) -> None:
        self._vol_threshold = volume_spike_threshold
        self._sentiment_threshold = sentiment_threshold

    async def evaluate(
        self, symbol: str, features: FeatureVector,
    ) -> Signal | None:
        vol_ratio = features.features.get("article_volume_ratio", 1.0)
        sentiment = features.features.get("sentiment_avg_6h", 0.0)
        velocity = features.features.get("sentiment_velocity", 0.0)

        if vol_ratio < self._vol_threshold:
            return None

        if abs(sentiment) < self._sentiment_threshold:
            return None

        direction = SignalDirection.BUY if sentiment > 0 else SignalDirection.SELL
        confidence = min((vol_ratio / self._vol_threshold) * abs(sentiment), 1.0)

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            strategy_name=self.name,
            reasoning=(
                f"Sentiment spike: {vol_ratio:.1f}x article volume, "
                f"sentiment={sentiment:.2f}, velocity={velocity:.2f}"
            ),
            timestamp=datetime.now(timezone.utc),
        )

    def required_features(self) -> list[str]:
        return ["article_volume_ratio", "sentiment_avg_6h", "sentiment_velocity"]
