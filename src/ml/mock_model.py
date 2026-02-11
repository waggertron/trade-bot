"""Mock ML model for testing."""

from __future__ import annotations

from src.ml.models import Dataset, EvalMetrics, FeatureVector, Prediction, TrainResult


class MockModel:
    """Mock model that returns configured predictions."""

    def __init__(
        self,
        default_direction: str = "hold",
        default_confidence: float = 0.5,
    ) -> None:
        self._direction = default_direction
        self._confidence = default_confidence
        self.predict_count: int = 0
        self.train_count: int = 0
        self.evaluate_count: int = 0

    @property
    def name(self) -> str:
        return "mock_model"

    async def predict(self, features: FeatureVector) -> Prediction:
        self.predict_count += 1
        return Prediction(
            direction=self._direction,
            confidence=self._confidence,
            model=self.name,
        )

    async def train(self, dataset: Dataset) -> TrainResult:
        self.train_count += 1
        return TrainResult(
            model=self.name,
            train_samples=len(dataset.vectors),
            train_accuracy=0.75,
        )

    async def evaluate(self, dataset: Dataset) -> EvalMetrics:
        self.evaluate_count += 1
        return EvalMetrics(
            model=self.name,
            accuracy=0.7,
            test_samples=len(dataset.vectors),
        )
