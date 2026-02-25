"""Ensemble model that combines predictions from multiple sub-models via weighted voting."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from src.ml.models import Dataset, EvalMetrics, FeatureVector, Prediction, TrainResult

logger = logging.getLogger(__name__)


class EnsembleModel:
    """Weighted ensemble that aggregates predictions from multiple ModelProvider instances."""

    def __init__(
        self,
        models: list,
        weights: list[float] | None = None,
    ) -> None:
        self._models = models
        if weights is None:
            n = len(models)
            self._weights = [1.0 / n] * n if n > 0 else []
        else:
            self._weights = weights

    @property
    def name(self) -> str:
        return "ensemble"

    async def predict(self, features: FeatureVector) -> Prediction:
        """Run all sub-models in parallel and combine via weighted voting."""
        if not self._models:
            return Prediction(direction="hold", confidence=0.5, model=self.name)

        # Gather predictions in parallel; capture exceptions individually
        results = await asyncio.gather(
            *[m.predict(features) for m in self._models],
            return_exceptions=True,
        )

        direction_scores: dict[str, float] = defaultdict(float)
        for pred, weight in zip(results, self._weights, strict=False):
            if isinstance(pred, BaseException):
                logger.warning("Sub-model predict failed: %s", pred)
                continue
            direction_scores[pred.direction] += pred.confidence * weight

        # If every model failed, fall back to hold
        if not direction_scores:
            return Prediction(direction="hold", confidence=0.5, model=self.name)

        winner = max(direction_scores, key=lambda d: direction_scores[d])
        total = sum(direction_scores.values())
        confidence = min(direction_scores[winner] / total, 1.0) if total > 0 else 0.5

        return Prediction(direction=winner, confidence=confidence, model=self.name)

    async def train(self, dataset: Dataset) -> TrainResult:
        """Train all sub-models sequentially and return averaged results."""
        if not self._models:
            return TrainResult(
                model=self.name,
                train_samples=len(dataset.vectors),
                train_accuracy=0.0,
            )

        accuracies: list[float] = []
        for m in self._models:
            result = await m.train(dataset)
            accuracies.append(result.train_accuracy)

        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.0

        return TrainResult(
            model=self.name,
            train_samples=len(dataset.vectors),
            train_accuracy=avg_accuracy,
        )

    async def evaluate(self, dataset: Dataset) -> EvalMetrics:
        """Evaluate all sub-models sequentially and return averaged metrics."""
        if not self._models:
            return EvalMetrics(
                model=self.name,
                test_samples=len(dataset.vectors),
                accuracy=0.0,
            )

        all_metrics: list[EvalMetrics] = []
        for m in self._models:
            result = await m.evaluate(dataset)
            all_metrics.append(result)

        n = len(all_metrics)
        avg_accuracy = sum(m.accuracy for m in all_metrics) / n
        avg_precision = sum(m.precision for m in all_metrics) / n
        avg_recall = sum(m.recall for m in all_metrics) / n
        avg_sharpe = sum(m.sharpe for m in all_metrics) / n

        return EvalMetrics(
            model=self.name,
            accuracy=avg_accuracy,
            precision=avg_precision,
            recall=avg_recall,
            sharpe=avg_sharpe,
            test_samples=len(dataset.vectors),
        )
