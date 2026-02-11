"""Tests for FeatureStore in-memory feature vector persistence."""

import pytest

from src.ml.feature_store import FeatureStore
from src.ml.models import FeatureVector


@pytest.fixture
def store() -> FeatureStore:
    """Return a fresh FeatureStore instance."""
    return FeatureStore()


@pytest.fixture
def populated_store(store: FeatureStore) -> FeatureStore:
    """Return a FeatureStore pre-loaded with test data."""
    store.save("AAPL", 1000, {"rsi": 55.0, "macd": 0.12})
    store.save("AAPL", 2000, {"rsi": 60.0, "macd": -0.05})
    store.save("AAPL", 3000, {"rsi": 45.0, "volume": 1500.0})
    store.save("BTC", 1000, {"rsi": 70.0, "momentum": 0.8})
    store.save("BTC", 2000, {"rsi": 65.0, "momentum": 0.5})
    return store


class TestSaveAndLoad:
    def test_save_and_load_single_entry(self, store: FeatureStore) -> None:
        store.save("AAPL", 1700000000, {"rsi": 55.0, "macd": 0.12})
        result = store.load("AAPL", 1700000000)
        assert result == {"rsi": 55.0, "macd": 0.12}

    def test_load_missing_returns_empty_dict(self, store: FeatureStore) -> None:
        result = store.load("AAPL", 9999999)
        assert result == {}

    def test_save_updates_existing_entry(self, store: FeatureStore) -> None:
        """Saving to an existing (symbol, timestamp) merges features."""
        store.save("AAPL", 1000, {"rsi": 55.0, "macd": 0.12})
        store.save("AAPL", 1000, {"volume": 1500.0, "rsi": 60.0})
        result = store.load("AAPL", 1000)
        # rsi should be updated, macd retained, volume added
        assert result == {"rsi": 60.0, "macd": 0.12, "volume": 1500.0}

    def test_load_returns_copy(self, store: FeatureStore) -> None:
        """Mutating a loaded dict should not affect the store."""
        store.save("AAPL", 1000, {"rsi": 55.0})
        loaded = store.load("AAPL", 1000)
        loaded["rsi"] = 999.0
        assert store.load("AAPL", 1000) == {"rsi": 55.0}


class TestLoadRange:
    def test_load_range_returns_sorted_results(
        self, populated_store: FeatureStore
    ) -> None:
        results = populated_store.load_range("AAPL", 1000, 3000)
        assert len(results) == 3
        timestamps = [r.timestamp for r in results]
        assert timestamps == [1000, 2000, 3000]

    def test_load_range_filters_by_time_range(
        self, populated_store: FeatureStore
    ) -> None:
        results = populated_store.load_range("AAPL", 1500, 2500)
        assert len(results) == 1
        assert results[0].timestamp == 2000
        assert results[0].symbol == "AAPL"

    def test_load_range_missing_symbol_returns_empty(
        self, populated_store: FeatureStore
    ) -> None:
        results = populated_store.load_range("ETH", 0, 99999)
        assert results == []

    def test_load_range_returns_feature_vectors(
        self, populated_store: FeatureStore
    ) -> None:
        results = populated_store.load_range("AAPL", 1000, 1000)
        assert len(results) == 1
        fv = results[0]
        assert isinstance(fv, FeatureVector)
        assert fv.symbol == "AAPL"
        assert fv.timestamp == 1000
        assert fv.features == {"rsi": 55.0, "macd": 0.12}


class TestFeatureNames:
    def test_feature_names_across_all_symbols(
        self, populated_store: FeatureStore
    ) -> None:
        names = populated_store.feature_names()
        assert names == {"rsi", "macd", "volume", "momentum"}

    def test_feature_names_filtered_by_symbol(
        self, populated_store: FeatureStore
    ) -> None:
        aapl_names = populated_store.feature_names(symbol="AAPL")
        assert aapl_names == {"rsi", "macd", "volume"}

        btc_names = populated_store.feature_names(symbol="BTC")
        assert btc_names == {"rsi", "momentum"}

    def test_feature_names_unknown_symbol_returns_empty(
        self, store: FeatureStore
    ) -> None:
        assert store.feature_names(symbol="ETH") == set()


class TestCount:
    def test_count_total(self, populated_store: FeatureStore) -> None:
        assert populated_store.count() == 5

    def test_count_by_symbol(self, populated_store: FeatureStore) -> None:
        assert populated_store.count(symbol="AAPL") == 3
        assert populated_store.count(symbol="BTC") == 2

    def test_count_unknown_symbol_returns_zero(
        self, populated_store: FeatureStore
    ) -> None:
        assert populated_store.count(symbol="ETH") == 0

    def test_count_empty_store(self, store: FeatureStore) -> None:
        assert store.count() == 0


class TestSymbols:
    def test_symbols_lists_unique_symbols(
        self, populated_store: FeatureStore
    ) -> None:
        syms = populated_store.symbols()
        assert sorted(syms) == ["AAPL", "BTC"]

    def test_symbols_empty_store(self, store: FeatureStore) -> None:
        assert store.symbols() == []
