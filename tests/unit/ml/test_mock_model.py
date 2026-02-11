"""Tests for MockModel implementation."""

from __future__ import annotations

import pytest

from src.ml.mock_model import MockModel
from src.ml.models import Dataset, EvalMetrics, FeatureVector, Prediction, TrainResult
from src.ml.protocols import ModelProvider


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


def _make_feature_vector() -> FeatureVector:
    return FeatureVector(
        symbol="BTC",
        timestamp=1700000000,
        features={"rsi": 55.0, "macd": 0.12},
    )


class TestMockModelProtocol:
    def test_implements_model_provider(self):
        """MockModel should satisfy the ModelProvider protocol."""
        model = MockModel()
        assert isinstance(model, ModelProvider)


class TestMockModelPredict:
    @pytest.mark.asyncio
    async def test_predict_returns_prediction(self):
        model = MockModel()
        result = await model.predict(_make_feature_vector())
        assert isinstance(result, Prediction)

    @pytest.mark.asyncio
    async def test_predict_default_direction_and_confidence(self):
        model = MockModel()
        result = await model.predict(_make_feature_vector())
        assert result.direction == "hold"
        assert result.confidence == 0.5
        assert result.model == "mock_model"

    @pytest.mark.asyncio
    async def test_predict_custom_direction_and_confidence(self):
        model = MockModel(default_direction="buy", default_confidence=0.9)
        result = await model.predict(_make_feature_vector())
        assert result.direction == "buy"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_predict_increments_count(self):
        model = MockModel()
        assert model.predict_count == 0
        await model.predict(_make_feature_vector())
        assert model.predict_count == 1
        await model.predict(_make_feature_vector())
        assert model.predict_count == 2


class TestMockModelTrain:
    @pytest.mark.asyncio
    async def test_train_returns_train_result(self):
        model = MockModel()
        ds = _make_dataset(5)
        result = await model.train(ds)
        assert isinstance(result, TrainResult)

    @pytest.mark.asyncio
    async def test_train_sample_count_matches_dataset(self):
        model = MockModel()
        ds = _make_dataset(7)
        result = await model.train(ds)
        assert result.train_samples == 7
        assert result.model == "mock_model"
        assert result.train_accuracy == 0.75

    @pytest.mark.asyncio
    async def test_train_increments_count(self):
        model = MockModel()
        ds = _make_dataset()
        assert model.train_count == 0
        await model.train(ds)
        assert model.train_count == 1
        await model.train(ds)
        assert model.train_count == 2


class TestMockModelEvaluate:
    @pytest.mark.asyncio
    async def test_evaluate_returns_eval_metrics(self):
        model = MockModel()
        ds = _make_dataset(10)
        result = await model.evaluate(ds)
        assert isinstance(result, EvalMetrics)

    @pytest.mark.asyncio
    async def test_evaluate_sample_count_matches_dataset(self):
        model = MockModel()
        ds = _make_dataset(10)
        result = await model.evaluate(ds)
        assert result.test_samples == 10
        assert result.model == "mock_model"
        assert result.accuracy == 0.7

    @pytest.mark.asyncio
    async def test_evaluate_increments_count(self):
        model = MockModel()
        ds = _make_dataset()
        assert model.evaluate_count == 0
        await model.evaluate(ds)
        assert model.evaluate_count == 1
        await model.evaluate(ds)
        assert model.evaluate_count == 2


class TestMockModelName:
    def test_name_property(self):
        model = MockModel()
        assert model.name == "mock_model"


class TestMockModelCallCounts:
    @pytest.mark.asyncio
    async def test_independent_call_counts(self):
        """All counters track independently."""
        model = MockModel()
        fv = _make_feature_vector()
        ds = _make_dataset()

        await model.predict(fv)
        await model.predict(fv)
        await model.train(ds)
        await model.evaluate(ds)

        assert model.predict_count == 2
        assert model.train_count == 1
        assert model.evaluate_count == 1
