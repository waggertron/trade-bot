"""Tests for LSTMModel implementation."""

from __future__ import annotations

import pytest

from src.ml.lstm_model import LSTMModel
from src.ml.models import Dataset, EvalMetrics, FeatureVector, Prediction, TrainResult
from src.ml.protocols import ModelProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_feature_vector(
    symbol: str = "BTC",
    ts: int = 1700000000,
    rsi: float = 55.0,
    macd: float = 0.12,
) -> FeatureVector:
    return FeatureVector(
        symbol=symbol,
        timestamp=ts,
        features={"rsi": rsi, "macd": macd},
    )


def _make_dataset(n: int = 30, feature_names: list[str] | None = None) -> Dataset:
    """Create a dataset with n vectors — enough for sequence_length=20 default."""
    fnames = feature_names or ["rsi", "macd"]
    vectors = [
        FeatureVector(
            symbol="BTC",
            timestamp=1700000000 + i,
            features={name: float(i) for name in fnames},
        )
        for i in range(n)
    ]
    labels = [i % 3 for i in range(n)]  # cycle through 0, 1, 2
    return Dataset(feature_names=fnames, vectors=vectors, labels=labels)


# ===========================================================================
# Tests that work WITHOUT torch
# ===========================================================================


class TestLSTMModelProtocol:
    def test_implements_model_provider(self):
        """LSTMModel satisfies the ModelProvider protocol."""
        model = LSTMModel()
        assert isinstance(model, ModelProvider)


class TestLSTMModelName:
    def test_name_property(self):
        model = LSTMModel()
        assert model.name == "lstm"


class TestVectorsToSequences:
    def test_correct_shapes(self):
        """Sliding window produces correct number of sequences."""
        fnames = ["rsi", "macd"]
        vectors = [
            FeatureVector(
                symbol="BTC",
                timestamp=1700000000 + i,
                features={"rsi": float(i), "macd": float(i * 2)},
            )
            for i in range(10)
        ]
        labels = list(range(10))

        X, y = LSTMModel._vectors_to_sequences(vectors, labels, fnames, seq_len=5)

        # 10 vectors with seq_len=5 -> 6 sequences (10 - 5 + 1)
        assert len(X) == 6
        assert len(y) == 6
        # Each sequence should have shape (seq_len, n_features)
        assert len(X[0]) == 5
        assert len(X[0][0]) == 2

    def test_label_is_last_in_window(self):
        """The label for each sequence should correspond to the last vector in that window."""
        fnames = ["f1"]
        vectors = [
            FeatureVector(symbol="BTC", timestamp=i, features={"f1": float(i)})
            for i in range(5)
        ]
        labels = [10, 20, 30, 40, 50]

        X, y = LSTMModel._vectors_to_sequences(vectors, labels, fnames, seq_len=3)

        # Sequences: [0,1,2], [1,2,3], [2,3,4] => labels at idx 2,3,4 => 30,40,50
        assert y == [30, 40, 50]

    def test_fewer_vectors_than_seq_len_returns_empty(self):
        """If there are fewer vectors than seq_len, returns empty lists."""
        fnames = ["rsi"]
        vectors = [
            FeatureVector(symbol="BTC", timestamp=i, features={"rsi": 1.0})
            for i in range(3)
        ]
        labels = [0, 1, 2]

        X, y = LSTMModel._vectors_to_sequences(vectors, labels, fnames, seq_len=10)

        assert X == []
        assert y == []

    def test_exact_seq_len_returns_one_sequence(self):
        """If vector count equals seq_len, exactly one sequence is produced."""
        fnames = ["a", "b"]
        vectors = [
            FeatureVector(symbol="BTC", timestamp=i, features={"a": 1.0, "b": 2.0})
            for i in range(5)
        ]
        labels = [0, 0, 1, 1, 2]

        X, y = LSTMModel._vectors_to_sequences(vectors, labels, fnames, seq_len=5)

        assert len(X) == 1
        assert len(y) == 1
        assert y[0] == 2  # label of last vector


class TestPredictWithoutTraining:
    @pytest.mark.asyncio
    async def test_returns_hold_with_half_confidence(self):
        """Predict without training returns hold/0.5 fallback."""
        model = LSTMModel()
        fv = _make_feature_vector()
        result = await model.predict(fv)

        assert isinstance(result, Prediction)
        assert result.direction == "hold"
        assert result.confidence == 0.5
        assert result.model == "lstm"


class TestBufferPerSymbol:
    @pytest.mark.asyncio
    async def test_buffers_are_per_symbol(self):
        """Adding to BTC buffer does not affect ETH buffer."""
        model = LSTMModel()
        model._feature_names = ["rsi", "macd"]

        btc_fv = _make_feature_vector(symbol="BTC")
        eth_fv = _make_feature_vector(symbol="ETH")

        # Predict on BTC twice
        await model.predict(btc_fv)
        await model.predict(btc_fv)

        assert len(model._buffers["BTC"]) == 2
        assert len(model._buffers["ETH"]) == 0

        # Now predict on ETH
        await model.predict(eth_fv)
        assert len(model._buffers["ETH"]) == 1
        assert len(model._buffers["BTC"]) == 2


class TestBufferTruncation:
    @pytest.mark.asyncio
    async def test_buffer_truncated_to_sequence_length(self):
        """Buffer should not grow beyond sequence_length."""
        model = LSTMModel(sequence_length=3)
        model._feature_names = ["rsi", "macd"]

        for i in range(10):
            fv = _make_feature_vector(ts=1700000000 + i, rsi=float(i))
            await model.predict(fv)

        assert len(model._buffers["BTC"]) == 3


# ===========================================================================
# Tests that NEED torch (will be skipped if torch is not installed)
# ===========================================================================


class TestLSTMModelTrainWithTorch:
    @pytest.mark.asyncio
    async def test_train_creates_network(self):
        """Training should create the LSTM network and set feature names."""
        torch = pytest.importorskip("torch")

        model = LSTMModel(sequence_length=5, epochs=2)
        ds = _make_dataset(n=20, feature_names=["rsi", "macd"])
        result = await model.train(ds)

        assert isinstance(result, TrainResult)
        assert result.model == "lstm"
        assert result.train_samples == 20
        assert model._network is not None
        assert model._feature_names == ["rsi", "macd"]

    @pytest.mark.asyncio
    async def test_train_accuracy_between_zero_and_one(self):
        """Training accuracy should be a valid float between 0 and 1."""
        torch = pytest.importorskip("torch")

        model = LSTMModel(sequence_length=5, epochs=5)
        ds = _make_dataset(n=20)
        result = await model.train(ds)

        assert 0.0 <= result.train_accuracy <= 1.0


class TestLSTMModelPredictWithTorch:
    @pytest.mark.asyncio
    async def test_predict_after_training(self):
        """After training and filling buffer, predict returns valid direction/confidence."""
        torch = pytest.importorskip("torch")

        seq_len = 5
        model = LSTMModel(sequence_length=seq_len, epochs=2)
        ds = _make_dataset(n=20, feature_names=["rsi", "macd"])
        await model.train(ds)

        # Fill buffer up to sequence_length
        for i in range(seq_len):
            fv = _make_feature_vector(ts=1700000000 + i, rsi=float(i * 10))
            result = await model.predict(fv)

        assert isinstance(result, Prediction)
        assert result.direction in ("buy", "sell", "hold")
        assert 0.0 <= result.confidence <= 1.0
        assert result.model == "lstm"

    @pytest.mark.asyncio
    async def test_predict_before_full_buffer_returns_hold(self):
        """Predict with partial buffer (not yet seq_len) returns hold."""
        torch = pytest.importorskip("torch")

        seq_len = 10
        model = LSTMModel(sequence_length=seq_len, epochs=2)
        ds = _make_dataset(n=30, feature_names=["rsi", "macd"])
        await model.train(ds)

        # Add fewer vectors than sequence_length
        for i in range(seq_len - 1):
            fv = _make_feature_vector(ts=1700000000 + i)
            result = await model.predict(fv)

        assert result.direction == "hold"
        assert result.confidence == 0.5


class TestLSTMModelEvaluateWithTorch:
    @pytest.mark.asyncio
    async def test_evaluate_returns_valid_metrics(self):
        """Evaluate after training returns valid EvalMetrics."""
        torch = pytest.importorskip("torch")

        model = LSTMModel(sequence_length=5, epochs=2)
        ds = _make_dataset(n=20, feature_names=["rsi", "macd"])
        await model.train(ds)

        result = await model.evaluate(ds)

        assert isinstance(result, EvalMetrics)
        assert result.model == "lstm"
        assert result.test_samples == 20
        assert 0.0 <= result.accuracy <= 1.0

    @pytest.mark.asyncio
    async def test_evaluate_without_training_returns_defaults(self):
        """Evaluate without training returns default EvalMetrics."""
        torch = pytest.importorskip("torch")

        model = LSTMModel()
        ds = _make_dataset(n=10)
        result = await model.evaluate(ds)

        assert isinstance(result, EvalMetrics)
        assert result.model == "lstm"
        assert result.test_samples == 10
        assert result.accuracy == 0.0
