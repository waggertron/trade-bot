"""Tests for ML pipeline Pydantic models."""

import pytest
from pydantic import ValidationError

from src.ml.models import Dataset, EvalMetrics, FeatureVector, Prediction, TrainResult

# ---------------------------------------------------------------------------
# FeatureVector
# ---------------------------------------------------------------------------


class TestFeatureVector:
    def test_creation(self):
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=1700000000,
            features={"rsi": 55.0, "macd": 0.12},
        )
        assert fv.symbol == "AAPL"
        assert fv.timestamp == 1700000000
        assert fv.features == {"rsi": 55.0, "macd": 0.12}

    def test_creation_default_features(self):
        fv = FeatureVector(symbol="BTC", timestamp=1700000000)
        assert fv.features == {}

    def test_to_array_ordering(self):
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=1700000000,
            features={"rsi": 55.0, "macd": 0.12, "volume": 1000.0},
        )
        result = fv.to_array(["volume", "rsi", "macd"])
        assert result == [1000.0, 55.0, 0.12]

    def test_to_array_missing_features_returns_zero(self):
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=1700000000,
            features={"rsi": 55.0},
        )
        result = fv.to_array(["rsi", "macd", "volume"])
        assert result == [55.0, 0.0, 0.0]

    def test_to_array_empty_feature_names(self):
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=1700000000,
            features={"rsi": 55.0},
        )
        assert fv.to_array([]) == []

    def test_subset_filtering(self):
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=1700000000,
            features={"rsi": 55.0, "macd": 0.12, "volume": 1000.0},
        )
        subset = fv.subset(["rsi", "volume"])
        assert subset.symbol == "AAPL"
        assert subset.timestamp == 1700000000
        assert subset.features == {"rsi": 55.0, "volume": 1000.0}

    def test_subset_with_missing_names(self):
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=1700000000,
            features={"rsi": 55.0},
        )
        subset = fv.subset(["rsi", "nonexistent"])
        assert subset.features == {"rsi": 55.0}

    def test_frozen(self):
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=1700000000,
            features={"rsi": 55.0},
        )
        with pytest.raises(ValidationError):
            fv.symbol = "GOOG"

    def test_serialization_roundtrip(self):
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=1700000000,
            features={"rsi": 55.0, "macd": 0.12},
        )
        data = fv.model_dump()
        restored = FeatureVector(**data)
        assert restored == fv

    def test_json_roundtrip(self):
        fv = FeatureVector(
            symbol="AAPL",
            timestamp=1700000000,
            features={"rsi": 55.0, "macd": 0.12},
        )
        json_str = fv.model_dump_json()
        restored = FeatureVector.model_validate_json(json_str)
        assert restored == fv


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------


class TestPrediction:
    def test_creation(self):
        pred = Prediction(
            direction="buy",
            confidence=0.85,
            model="random_forest",
            features_used=["rsi", "macd"],
        )
        assert pred.direction == "buy"
        assert pred.confidence == 0.85
        assert pred.model == "random_forest"
        assert pred.features_used == ["rsi", "macd"]

    def test_creation_defaults(self):
        pred = Prediction(direction="hold", confidence=0.5, model="svm")
        assert pred.features_used == []

    def test_confidence_lower_bound(self):
        with pytest.raises(ValidationError):
            Prediction(direction="buy", confidence=-0.1, model="svm")

    def test_confidence_upper_bound(self):
        with pytest.raises(ValidationError):
            Prediction(direction="buy", confidence=1.1, model="svm")

    def test_confidence_at_bounds(self):
        pred_low = Prediction(direction="buy", confidence=0.0, model="svm")
        pred_high = Prediction(direction="sell", confidence=1.0, model="svm")
        assert pred_low.confidence == 0.0
        assert pred_high.confidence == 1.0

    def test_frozen(self):
        pred = Prediction(direction="buy", confidence=0.85, model="rf")
        with pytest.raises(ValidationError):
            pred.direction = "sell"


# ---------------------------------------------------------------------------
# TrainResult
# ---------------------------------------------------------------------------


class TestTrainResult:
    def test_creation(self):
        result = TrainResult(
            model="random_forest",
            feature_importance={"rsi": 0.4, "macd": 0.6},
            train_samples=1000,
            train_accuracy=0.92,
        )
        assert result.model == "random_forest"
        assert result.feature_importance == {"rsi": 0.4, "macd": 0.6}
        assert result.train_samples == 1000
        assert result.train_accuracy == 0.92

    def test_defaults(self):
        result = TrainResult(model="svm")
        assert result.feature_importance == {}
        assert result.train_samples == 0
        assert result.train_accuracy == 0.0

    def test_frozen(self):
        result = TrainResult(model="svm")
        with pytest.raises(ValidationError):
            result.model = "rf"


# ---------------------------------------------------------------------------
# EvalMetrics
# ---------------------------------------------------------------------------


class TestEvalMetrics:
    def test_creation(self):
        metrics = EvalMetrics(
            model="random_forest",
            accuracy=0.88,
            precision=0.85,
            recall=0.90,
            sharpe=1.5,
            test_samples=200,
        )
        assert metrics.model == "random_forest"
        assert metrics.accuracy == 0.88
        assert metrics.precision == 0.85
        assert metrics.recall == 0.90
        assert metrics.sharpe == 1.5
        assert metrics.test_samples == 200

    def test_defaults(self):
        metrics = EvalMetrics(model="svm")
        assert metrics.accuracy == 0.0
        assert metrics.precision == 0.0
        assert metrics.recall == 0.0
        assert metrics.sharpe == 0.0
        assert metrics.test_samples == 0

    def test_frozen(self):
        metrics = EvalMetrics(model="svm")
        with pytest.raises(ValidationError):
            metrics.accuracy = 0.99


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------


class TestDataset:
    def test_creation(self):
        fv1 = FeatureVector(
            symbol="AAPL", timestamp=1700000000, features={"rsi": 55.0, "macd": 0.12}
        )
        fv2 = FeatureVector(
            symbol="AAPL", timestamp=1700000001, features={"rsi": 60.0, "macd": -0.05}
        )
        ds = Dataset(
            feature_names=["rsi", "macd"],
            vectors=[fv1, fv2],
            labels=[0, 1],
        )
        assert len(ds.vectors) == 2
        assert ds.labels == [0, 1]
        assert ds.feature_names == ["rsi", "macd"]

    def test_to_arrays(self):
        fv1 = FeatureVector(
            symbol="AAPL", timestamp=1700000000, features={"rsi": 55.0, "macd": 0.12}
        )
        fv2 = FeatureVector(
            symbol="AAPL", timestamp=1700000001, features={"rsi": 60.0, "macd": -0.05}
        )
        ds = Dataset(
            feature_names=["rsi", "macd"],
            vectors=[fv1, fv2],
            labels=[0, 1],
        )
        X, y = ds.to_arrays()
        assert X == [[55.0, 0.12], [60.0, -0.05]]
        assert y == [0, 1]

    def test_to_arrays_with_missing_features(self):
        fv = FeatureVector(symbol="AAPL", timestamp=1700000000, features={"rsi": 55.0})
        ds = Dataset(
            feature_names=["rsi", "macd"],
            vectors=[fv],
            labels=[0],
        )
        X, y = ds.to_arrays()
        assert X == [[55.0, 0.0]]
        assert y == [0]

    def test_empty_dataset(self):
        ds = Dataset()
        assert ds.feature_names == []
        assert ds.vectors == []
        assert ds.labels == []
        X, y = ds.to_arrays()
        assert X == []
        assert y == []

    def test_mutable(self):
        """Dataset is NOT frozen -- it should be mutable for building."""
        ds = Dataset()
        ds.feature_names = ["rsi"]
        fv = FeatureVector(symbol="AAPL", timestamp=1700000000, features={"rsi": 55.0})
        ds.vectors.append(fv)
        ds.labels.append(0)
        assert len(ds.vectors) == 1
        assert ds.labels == [0]
