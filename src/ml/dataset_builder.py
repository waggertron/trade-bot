"""Builds ML datasets from feature store data."""
from __future__ import annotations

from collections.abc import Callable

from src.ml.feature_store import FeatureStore
from src.ml.models import Dataset, FeatureVector


def default_label_fn(vectors: list[FeatureVector]) -> list[int]:
    """Default labeling: next-period close direction.

    Compares the 'close' feature of each vector to the next one.
    0=buy (price will go up), 1=sell (price will go down), 2=hold (flat).
    The last vector gets label 2 (hold) since there's no next period.
    """
    labels: list[int] = []
    for i in range(len(vectors)):
        if i + 1 >= len(vectors):
            labels.append(2)  # hold for last
            continue
        current_close = vectors[i].features.get("close", 0.0)
        next_close = vectors[i + 1].features.get("close", 0.0)
        if current_close == 0:
            labels.append(2)
        elif next_close > current_close * 1.001:  # > 0.1% up
            labels.append(0)  # buy
        elif next_close < current_close * 0.999:  # > 0.1% down
            labels.append(1)  # sell
        else:
            labels.append(2)  # hold
    return labels


class DatasetBuilder:
    """Builds Dataset objects from FeatureStore data."""

    def __init__(
        self,
        store: FeatureStore,
        label_fn: Callable[[list[FeatureVector]], list[int]] | None = None,
    ) -> None:
        self._store = store
        self._label_fn = label_fn or default_label_fn

    def build(
        self,
        symbols: list[str],
        start_ts: int,
        end_ts: int,
        feature_names: list[str],
    ) -> Dataset:
        """Build a dataset from stored feature vectors.

        Loads vectors for each symbol in the time range,
        applies the label function, and returns a Dataset.
        """
        all_vectors: list[FeatureVector] = []
        all_labels: list[int] = []

        for symbol in symbols:
            vectors = self._store.load_range(symbol, start_ts, end_ts)
            if not vectors:
                continue
            labels = self._label_fn(vectors)
            all_vectors.extend(vectors)
            all_labels.extend(labels)

        return Dataset(
            feature_names=feature_names,
            vectors=all_vectors,
            labels=all_labels,
        )
