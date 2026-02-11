"""End-to-end integration test for Feature Store & ML Pipeline."""
import pytest
import numpy as np

from src.ml.feature_engine import FeatureEngine
from src.ml.feature_store import FeatureStore
from src.ml.dataset_builder import DatasetBuilder
from src.ml.mock_model import MockModel
from src.ml.trainer import WalkForwardTrainer
from src.providers.technical import TechnicalFeatureProvider
from src.providers.configs import TechnicalFeatureConfig
from src.providers.mock import MockFeatureProvider


def _make_ohlcv(n=200, start=100.0):
    """Generate synthetic OHLCV data."""
    np.random.seed(42)
    close = np.cumsum(np.random.randn(n) * 2 + 0.05) + start
    high = close + np.abs(np.random.randn(n))
    low = close - np.abs(np.random.randn(n))
    volume = np.random.randint(1000, 10000, n).astype(float)
    return {"close": close, "high": high, "low": low, "volume": volume}


class TestFeaturePipelineE2E:
    """Full integration: compute features -> store -> dataset -> train -> evaluate."""

    @pytest.mark.asyncio
    async def test_technical_features_to_store(self):
        """Compute technical features and verify they're stored."""
        store = FeatureStore()
        provider = TechnicalFeatureProvider(TechnicalFeatureConfig(indicators=["sma", "rsi"]))
        engine = FeatureEngine(providers=[provider], store=store)

        data = _make_ohlcv(100)
        vector = await engine.compute_and_store("AAPL", data, 1000)

        assert "sma_14" in vector.features
        assert "rsi_14" in vector.features
        assert store.count() == 1

    @pytest.mark.asyncio
    async def test_multiple_providers_merge(self):
        """Multiple providers merge features into single vector."""
        store = FeatureStore()
        tech = TechnicalFeatureProvider(TechnicalFeatureConfig(indicators=["rsi"]))
        mock = MockFeatureProvider()
        mock.set_features({"sentiment_avg": 0.7, "article_count": 5.0})
        engine = FeatureEngine(providers=[tech, mock], store=store)

        data = _make_ohlcv(100)
        vector = await engine.compute_and_store("AAPL", data, 1000)

        assert "rsi_14" in vector.features     # from technical
        assert "sentiment_avg" in vector.features  # from mock

    @pytest.mark.asyncio
    async def test_store_to_dataset(self):
        """Build a dataset from stored feature vectors."""
        store = FeatureStore()
        provider = TechnicalFeatureProvider(TechnicalFeatureConfig(indicators=["sma", "rsi"]))
        engine = FeatureEngine(providers=[provider], store=store)

        # Compute features for multiple timestamps
        data = _make_ohlcv(100)
        for i in range(20):
            # Use a sliding window of the price data
            window = {k: v[i:i+50] for k, v in data.items()}
            await engine.compute_and_store("AAPL", window, 1000 + i * 60)

        # Build dataset
        builder = DatasetBuilder(store=store)
        ds = builder.build(["AAPL"], 1000, 2200, ["sma_14", "rsi_14"])
        assert len(ds.vectors) > 0
        assert len(ds.labels) == len(ds.vectors)

    @pytest.mark.asyncio
    async def test_full_walk_forward(self):
        """Full pipeline: features -> store -> walk-forward training."""
        store = FeatureStore()

        # Populate store with feature vectors (simulating computed features)
        for i in range(100):
            store.save("AAPL", i * 60, {
                "close": 100.0 + i * 0.5,
                "rsi_14": 50.0 + (i % 20) - 10,
                "sma_14": 100.0 + i * 0.3,
            })

        model = MockModel(default_direction="buy", default_confidence=0.7)
        trainer = WalkForwardTrainer(
            model=model,
            store=store,
            train_window=3600,   # 60 min
            test_window=1200,    # 20 min
            step_size=1200,      # 20 min step
        )

        results = await trainer.run(["AAPL"], 0, 6000, ["close", "rsi_14", "sma_14"])

        assert len(results) > 0
        for r in results:
            assert r.train_result.model == "mock_model"
            assert r.eval_result.model == "mock_model"
            assert r.train_period[0] < r.train_period[1]
            assert r.test_period[0] < r.test_period[1]

    @pytest.mark.asyncio
    async def test_model_prediction_from_stored_features(self):
        """Retrieve stored features and get model prediction."""
        store = FeatureStore()
        provider = TechnicalFeatureProvider(TechnicalFeatureConfig(indicators=["rsi"]))
        engine = FeatureEngine(providers=[provider], store=store)

        data = _make_ohlcv(100)
        await engine.compute_and_store("AAPL", data, 1000)

        # Retrieve and predict
        vector = await engine.get_vector("AAPL", 1000)
        model = MockModel(default_direction="buy")
        prediction = await model.predict(vector)

        assert prediction.direction == "buy"
        assert prediction.model == "mock_model"
