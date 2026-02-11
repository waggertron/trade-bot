"""ML ensemble strategy that delegates to a ModelProvider for predictions."""

from __future__ import annotations

from datetime import datetime, timezone

from src.core.models import Signal, SignalDirection
from src.ml.models import FeatureVector


class MLEnsembleStrategy:
    """Strategy that wraps an ML model behind the FeatureStrategy protocol.

    Accepts any object with an async ``predict(features) -> Prediction`` method
    (i.e. anything satisfying the ``ModelProvider`` protocol).
    """

    name: str = "ml_ensemble"

    def __init__(
        self,
        model: object,
        min_confidence: float = 0.55,
    ) -> None:
        self._model = model
        self._min_confidence = min_confidence

    def required_features(self) -> list[str]:
        """Return an empty list — this strategy uses all available features."""
        return []

    async def evaluate(
        self,
        symbol: str,
        features: FeatureVector,
    ) -> Signal | None:
        prediction = await self._model.predict(features)

        if prediction.direction == "hold":
            return None

        if prediction.confidence < self._min_confidence:
            return None

        direction = SignalDirection[prediction.direction.upper()]

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=prediction.confidence,
            strategy_name=self.name,
            reasoning=f"ML ensemble: {prediction.direction} with {prediction.confidence:.2f} confidence",
            timestamp=datetime.now(timezone.utc),
        )
