"""Tests for EnsembleModel implementation."""

from __future__ import annotations

import pytest

from src.ml.ensemble import EnsembleModel
from src.ml.mock_model import MockModel
from src.ml.models import Dataset, EvalMetrics, FeatureVector, Prediction, TrainResult
from src.ml.protocols import ModelProvider


def _make_feature_vector() -> FeatureVector:
    return FeatureVector(
        symbol="BTC",
        timestamp=1700000000,
        features={"rsi": 55.0, "macd": 0.12},
    )


def _make_dataset(n: int = 3) -> Dataset:
    """Create a small dataset with n feature vectors."""
    vectors = [
        FeatureVector(
            symbol="BTC",
            timestamp=1700000000 + i,
            features={"rsi": 50.0 + i, "macd": 0.1 * i},
        )
        for i in range(n)
    ]
    labels = [0] * n
    return Dataset(feature_names=["rsi", "macd"], vectors=vectors, labels=labels)


class _FailingModel:
    """A model whose predict raises an exception."""

    @property
    def name(self) -> str:
        return "failing_model"

    async def predict(self, features: FeatureVector) -> Prediction:
        raise RuntimeError("predict exploded")

    async def train(self, dataset: Dataset) -> TrainResult:
        return TrainResult(model=self.name, train_samples=len(dataset.vectors), train_accuracy=0.0)

    async def evaluate(self, dataset: Dataset) -> EvalMetrics:
        return EvalMetrics(model=self.name, accuracy=0.0, test_samples=len(dataset.vectors))


class TestEnsembleProtocol:
    def test_implements_model_provider(self):
        """EnsembleModel should satisfy the ModelProvider protocol."""
        ensemble = EnsembleModel(models=[MockModel()])
        assert isinstance(ensemble, ModelProvider)


class TestEnsembleName:
    def test_name_property(self):
        ensemble = EnsembleModel(models=[])
        assert ensemble.name == "ensemble"


class TestEnsemblePredict:
    @pytest.mark.asyncio
    async def test_single_model_returns_its_direction(self):
        """With one model, ensemble returns that model's prediction direction."""
        model = MockModel(default_direction="buy", default_confidence=0.8)
        ensemble = EnsembleModel(models=[model])

        result = await ensemble.predict(_make_feature_vector())

        assert isinstance(result, Prediction)
        assert result.direction == "buy"
        assert result.model == "ensemble"

    @pytest.mark.asyncio
    async def test_two_models_same_direction_combines_confidences(self):
        """Two models predicting the same direction should combine their scores."""
        m1 = MockModel(default_direction="sell", default_confidence=0.7)
        m2 = MockModel(default_direction="sell", default_confidence=0.9)
        ensemble = EnsembleModel(models=[m1, m2])

        result = await ensemble.predict(_make_feature_vector())

        assert result.direction == "sell"
        # Both vote sell with uniform weights (0.5 each):
        # sell_score = 0.7*0.5 + 0.9*0.5 = 0.8
        # total = 0.8
        # confidence = 0.8 / 0.8 = 1.0
        assert result.confidence == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_two_models_different_directions_higher_score_wins(self):
        """When models disagree, the direction with higher weighted score wins."""
        m1 = MockModel(default_direction="buy", default_confidence=0.9)
        m2 = MockModel(default_direction="sell", default_confidence=0.3)
        ensemble = EnsembleModel(models=[m1, m2])

        result = await ensemble.predict(_make_feature_vector())

        assert result.direction == "buy"
        # Uniform weight = 0.5 each
        # buy_score = 0.9 * 0.5 = 0.45
        # sell_score = 0.3 * 0.5 = 0.15
        # total = 0.60
        # confidence = 0.45 / 0.60 = 0.75
        assert result.confidence == pytest.approx(0.75)

    @pytest.mark.asyncio
    async def test_custom_weights_amplify_weighted_model(self):
        """Custom weights should amplify the more-weighted model."""
        m1 = MockModel(default_direction="buy", default_confidence=0.6)
        m2 = MockModel(default_direction="sell", default_confidence=0.6)
        # Give m2 (sell) 3x the weight of m1 (buy)
        ensemble = EnsembleModel(models=[m1, m2], weights=[0.25, 0.75])

        result = await ensemble.predict(_make_feature_vector())

        assert result.direction == "sell"
        # buy_score = 0.6 * 0.25 = 0.15
        # sell_score = 0.6 * 0.75 = 0.45
        # total = 0.60
        # confidence = 0.45 / 0.60 = 0.75
        assert result.confidence == pytest.approx(0.75)

    @pytest.mark.asyncio
    async def test_predict_delegates_to_all_models(self):
        """Predict should call predict on every sub-model."""
        m1 = MockModel()
        m2 = MockModel()
        m3 = MockModel()
        ensemble = EnsembleModel(models=[m1, m2, m3])

        await ensemble.predict(_make_feature_vector())

        assert m1.predict_count == 1
        assert m2.predict_count == 1
        assert m3.predict_count == 1

    @pytest.mark.asyncio
    async def test_empty_models_predict_returns_hold(self):
        """With no models, predict returns hold with 0.5 confidence."""
        ensemble = EnsembleModel(models=[])

        result = await ensemble.predict(_make_feature_vector())

        assert result.direction == "hold"
        assert result.confidence == 0.5
        assert result.model == "ensemble"

    @pytest.mark.asyncio
    async def test_handles_model_predict_failure_gracefully(self):
        """If a model's predict raises, it should be skipped gracefully."""
        good = MockModel(default_direction="buy", default_confidence=0.8)
        bad = _FailingModel()
        ensemble = EnsembleModel(models=[good, bad])

        result = await ensemble.predict(_make_feature_vector())

        assert result.direction == "buy"
        assert result.model == "ensemble"

    @pytest.mark.asyncio
    async def test_all_models_fail_returns_hold(self):
        """If all models fail, predict returns hold/0.5."""
        bad1 = _FailingModel()
        bad2 = _FailingModel()
        ensemble = EnsembleModel(models=[bad1, bad2])

        result = await ensemble.predict(_make_feature_vector())

        assert result.direction == "hold"
        assert result.confidence == 0.5


class TestEnsembleTrain:
    @pytest.mark.asyncio
    async def test_train_delegates_to_all_sub_models(self):
        """Train should call train on every sub-model."""
        m1 = MockModel()
        m2 = MockModel()
        m3 = MockModel()
        ensemble = EnsembleModel(models=[m1, m2, m3])
        ds = _make_dataset(5)

        result = await ensemble.train(ds)

        assert m1.train_count == 1
        assert m2.train_count == 1
        assert m3.train_count == 1
        assert isinstance(result, TrainResult)
        assert result.model == "ensemble"
        assert result.train_samples == 5

    @pytest.mark.asyncio
    async def test_train_averages_accuracy(self):
        """Train should average the sub-model accuracies."""
        m1 = MockModel()  # returns train_accuracy=0.75
        m2 = MockModel()  # returns train_accuracy=0.75
        ensemble = EnsembleModel(models=[m1, m2])
        ds = _make_dataset(3)

        result = await ensemble.train(ds)

        assert result.train_accuracy == pytest.approx(0.75)

    @pytest.mark.asyncio
    async def test_train_empty_models_returns_defaults(self):
        """Training with no models returns default TrainResult."""
        ensemble = EnsembleModel(models=[])
        ds = _make_dataset(3)

        result = await ensemble.train(ds)

        assert result.model == "ensemble"
        assert result.train_samples == 3
        assert result.train_accuracy == 0.0


class TestEnsembleEvaluate:
    @pytest.mark.asyncio
    async def test_evaluate_delegates_to_all_sub_models(self):
        """Evaluate should call evaluate on every sub-model."""
        m1 = MockModel()
        m2 = MockModel()
        m3 = MockModel()
        ensemble = EnsembleModel(models=[m1, m2, m3])
        ds = _make_dataset(10)

        result = await ensemble.evaluate(ds)

        assert m1.evaluate_count == 1
        assert m2.evaluate_count == 1
        assert m3.evaluate_count == 1
        assert isinstance(result, EvalMetrics)
        assert result.model == "ensemble"
        assert result.test_samples == 10

    @pytest.mark.asyncio
    async def test_evaluate_averages_metrics(self):
        """Evaluate should average the sub-model metrics."""
        m1 = MockModel()  # returns accuracy=0.7
        m2 = MockModel()  # returns accuracy=0.7
        ensemble = EnsembleModel(models=[m1, m2])
        ds = _make_dataset(10)

        result = await ensemble.evaluate(ds)

        assert result.accuracy == pytest.approx(0.7)

    @pytest.mark.asyncio
    async def test_evaluate_empty_models_returns_defaults(self):
        """Evaluating with no models returns default EvalMetrics."""
        ensemble = EnsembleModel(models=[])
        ds = _make_dataset(5)

        result = await ensemble.evaluate(ds)

        assert result.model == "ensemble"
        assert result.test_samples == 5
        assert result.accuracy == 0.0
