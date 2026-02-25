"""Tests for FeatureEngine parallel feature computation and storage."""

import pytest

from src.ml.feature_engine import FeatureEngine
from src.ml.feature_store import FeatureStore
from src.ml.models import FeatureVector
from src.providers.mock import MockFeatureProvider


class FailingProvider:
    """A feature provider that always raises an error."""

    @property
    def name(self) -> str:
        return "failing"

    @property
    def required_inputs(self) -> list[str]:
        return []

    async def compute(self, inputs: dict) -> dict[str, float]:
        raise RuntimeError("boom")


@pytest.fixture
def store() -> FeatureStore:
    """Return a fresh FeatureStore instance."""
    return FeatureStore()


class TestComputeAndStore:
    @pytest.mark.asyncio
    async def test_single_provider(self, store: FeatureStore) -> None:
        """Computes features from a single mock provider."""
        provider = MockFeatureProvider()
        provider.set_features({"rsi_14": 55.0, "sma_14": 100.5})
        engine = FeatureEngine(providers=[provider], store=store)

        vector = await engine.compute_and_store("AAPL", {}, 1000)

        assert isinstance(vector, FeatureVector)
        assert vector.symbol == "AAPL"
        assert vector.timestamp == 1000
        assert vector.features == {"rsi_14": 55.0, "sma_14": 100.5}

    @pytest.mark.asyncio
    async def test_merges_multiple_providers(self, store: FeatureStore) -> None:
        """Merges results from multiple mock providers."""
        provider_a = MockFeatureProvider()
        provider_a.set_features({"rsi_14": 55.0})

        provider_b = MockFeatureProvider()
        provider_b.set_features({"volume_sma": 1200.0, "macd": 0.05})

        engine = FeatureEngine(providers=[provider_a, provider_b], store=store)

        vector = await engine.compute_and_store("BTC", {"price": 50000}, 2000)

        assert vector.features == {
            "rsi_14": 55.0,
            "volume_sma": 1200.0,
            "macd": 0.05,
        }

    @pytest.mark.asyncio
    async def test_handles_provider_failure_gracefully(self, store: FeatureStore) -> None:
        """Skips failed provider and keeps results from successful ones."""
        good_provider = MockFeatureProvider()
        good_provider.set_features({"rsi_14": 55.0})

        failing_provider = FailingProvider()

        engine = FeatureEngine(providers=[good_provider, failing_provider], store=store)

        vector = await engine.compute_and_store("AAPL", {}, 3000)

        # Should still have the good provider's features
        assert vector.features == {"rsi_14": 55.0}

    @pytest.mark.asyncio
    async def test_persists_to_store(self, store: FeatureStore) -> None:
        """Features are persisted in the store after compute."""
        provider = MockFeatureProvider()
        provider.set_features({"rsi_14": 55.0, "sma_14": 100.5})
        engine = FeatureEngine(providers=[provider], store=store)

        await engine.compute_and_store("AAPL", {}, 1000)

        stored = store.load("AAPL", 1000)
        assert stored == {"rsi_14": 55.0, "sma_14": 100.5}

    @pytest.mark.asyncio
    async def test_empty_providers_returns_empty_features(self, store: FeatureStore) -> None:
        """No providers means empty features dict."""
        engine = FeatureEngine(providers=[], store=store)

        vector = await engine.compute_and_store("AAPL", {}, 5000)

        assert vector.features == {}
        assert vector.symbol == "AAPL"
        assert vector.timestamp == 5000


class TestGetVector:
    @pytest.mark.asyncio
    async def test_retrieves_stored_data(self, store: FeatureStore) -> None:
        """get_vector retrieves previously stored feature data."""
        provider = MockFeatureProvider()
        provider.set_features({"rsi_14": 55.0, "sma_14": 100.5})
        engine = FeatureEngine(providers=[provider], store=store)

        await engine.compute_and_store("AAPL", {}, 1000)

        vector = await engine.get_vector("AAPL", 1000)

        assert isinstance(vector, FeatureVector)
        assert vector.symbol == "AAPL"
        assert vector.timestamp == 1000
        assert vector.features == {"rsi_14": 55.0, "sma_14": 100.5}

    @pytest.mark.asyncio
    async def test_get_vector_missing_returns_empty_features(self, store: FeatureStore) -> None:
        """get_vector for missing data returns empty features."""
        engine = FeatureEngine(providers=[], store=store)

        vector = await engine.get_vector("AAPL", 9999)

        assert vector.features == {}
        assert vector.symbol == "AAPL"
        assert vector.timestamp == 9999
