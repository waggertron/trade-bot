import pytest

from src.ml.feature_store import FeatureStore
from src.ml.models import FeatureVector


def _populate_store(store, symbol="AAPL", n=10, base_price=100.0):
    """Add n feature vectors with incrementing close prices."""
    for i in range(n):
        store.save(
            symbol,
            1000 + i * 60,
            {
                "close": base_price + i,
                "rsi_14": 50.0 + i,
                "sma_14": base_price + i * 0.5,
            },
        )


class TestDefaultLabelFn:
    def test_labels_up_as_buy(self):
        from src.ml.dataset_builder import default_label_fn

        vectors = [
            FeatureVector(symbol="A", timestamp=1000, features={"close": 100.0}),
            FeatureVector(symbol="A", timestamp=1060, features={"close": 102.0}),  # up >0.1%
        ]
        labels = default_label_fn(vectors)
        assert labels[0] == 0  # buy (price going up)
        assert labels[1] == 2  # hold (last vector)

    def test_labels_down_as_sell(self):
        from src.ml.dataset_builder import default_label_fn

        vectors = [
            FeatureVector(symbol="A", timestamp=1000, features={"close": 100.0}),
            FeatureVector(symbol="A", timestamp=1060, features={"close": 98.0}),  # down >0.1%
        ]
        labels = default_label_fn(vectors)
        assert labels[0] == 1  # sell

    def test_labels_flat_as_hold(self):
        from src.ml.dataset_builder import default_label_fn

        vectors = [
            FeatureVector(symbol="A", timestamp=1000, features={"close": 100.0}),
            FeatureVector(symbol="A", timestamp=1060, features={"close": 100.05}),  # < 0.1%
        ]
        labels = default_label_fn(vectors)
        assert labels[0] == 2  # hold

    def test_last_vector_always_hold(self):
        from src.ml.dataset_builder import default_label_fn

        vectors = [
            FeatureVector(symbol="A", timestamp=1000, features={"close": 100.0}),
        ]
        labels = default_label_fn(vectors)
        assert labels[0] == 2


class TestDatasetBuilder:
    @pytest.fixture
    def store(self):
        s = FeatureStore()
        _populate_store(s, "AAPL", 10, 100.0)
        return s

    def test_builds_dataset_from_store(self, store):
        from src.ml.dataset_builder import DatasetBuilder

        builder = DatasetBuilder(store=store)
        ds = builder.build(["AAPL"], 1000, 1600, ["close", "rsi_14"])
        assert len(ds.vectors) == 10
        assert len(ds.labels) == 10
        assert ds.feature_names == ["close", "rsi_14"]

    def test_respects_time_range(self, store):
        from src.ml.dataset_builder import DatasetBuilder

        builder = DatasetBuilder(store=store)
        ds = builder.build(["AAPL"], 1000, 1200, ["close"])
        assert len(ds.vectors) < 10  # only a subset

    def test_empty_data_returns_empty_dataset(self):
        from src.ml.dataset_builder import DatasetBuilder

        store = FeatureStore()
        builder = DatasetBuilder(store=store)
        ds = builder.build(["AAPL"], 1000, 2000, ["close"])
        assert len(ds.vectors) == 0
        assert len(ds.labels) == 0

    def test_multiple_symbols(self, store):
        from src.ml.dataset_builder import DatasetBuilder

        _populate_store(store, "GOOG", 5, 200.0)
        builder = DatasetBuilder(store=store)
        ds = builder.build(["AAPL", "GOOG"], 1000, 2000, ["close"])
        assert len(ds.vectors) == 15  # 10 AAPL + 5 GOOG

    def test_custom_label_fn(self, store):
        from src.ml.dataset_builder import DatasetBuilder

        # Custom: always label as buy (0)
        builder = DatasetBuilder(store=store, label_fn=lambda vecs: [0] * len(vecs))
        ds = builder.build(["AAPL"], 1000, 2000, ["close"])
        assert all(label == 0 for label in ds.labels)

    def test_to_arrays_works_on_built_dataset(self, store):
        from src.ml.dataset_builder import DatasetBuilder

        builder = DatasetBuilder(store=store)
        ds = builder.build(["AAPL"], 1000, 2000, ["close", "rsi_14"])
        X, y = ds.to_arrays()
        assert len(X) == len(y) == 10
        assert len(X[0]) == 2  # two features
