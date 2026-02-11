"""In-memory feature vector storage."""

from __future__ import annotations

from src.ml.models import FeatureVector


class FeatureStore:
    """In-memory feature vector storage.

    Stores feature dictionaries keyed by (symbol, timestamp) pairs.
    Supports saving, loading, range queries, and introspection.
    """

    def __init__(self) -> None:
        self._data: dict[tuple[str, int], dict[str, float]] = {}

    def save(self, symbol: str, timestamp: int, features: dict[str, float]) -> None:
        """Save or update features for a symbol at a timestamp.

        If an entry already exists for (symbol, timestamp), the new features
        are merged into the existing dict (updating existing keys and adding
        new ones).
        """
        key = (symbol, timestamp)
        if key in self._data:
            self._data[key].update(features)
        else:
            self._data[key] = dict(features)

    def load(self, symbol: str, timestamp: int) -> dict[str, float]:
        """Load features for a symbol at a timestamp.

        Returns a copy of the stored features, or an empty dict if not found.
        """
        return dict(self._data.get((symbol, timestamp), {}))

    def load_range(
        self, symbol: str, start_ts: int, end_ts: int
    ) -> list[FeatureVector]:
        """Load all feature vectors for symbol in [start_ts, end_ts], sorted by timestamp."""
        results: list[FeatureVector] = []
        for (sym, ts), features in self._data.items():
            if sym == symbol and start_ts <= ts <= end_ts:
                results.append(
                    FeatureVector(symbol=sym, timestamp=ts, features=features)
                )
        results.sort(key=lambda v: v.timestamp)
        return results

    def feature_names(self, symbol: str | None = None) -> set[str]:
        """All known feature names, optionally filtered by symbol."""
        names: set[str] = set()
        for (sym, _), features in self._data.items():
            if symbol is None or sym == symbol:
                names.update(features.keys())
        return names

    def count(self, symbol: str | None = None) -> int:
        """Count stored feature vectors, optionally filtered by symbol."""
        if symbol is None:
            return len(self._data)
        return sum(1 for (sym, _) in self._data if sym == symbol)

    def symbols(self) -> list[str]:
        """List all symbols with stored features."""
        return list({sym for sym, _ in self._data})
