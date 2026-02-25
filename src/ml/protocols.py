"""ML model protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.ml.models import Dataset, EvalMetrics, FeatureVector, Prediction, TrainResult


@runtime_checkable
class ModelProvider(Protocol):
    """Protocol for ML models that can predict, train, and evaluate."""

    @property
    def name(self) -> str: ...

    async def predict(self, features: FeatureVector) -> Prediction: ...

    async def train(self, dataset: Dataset) -> TrainResult: ...

    async def evaluate(self, dataset: Dataset) -> EvalMetrics: ...
