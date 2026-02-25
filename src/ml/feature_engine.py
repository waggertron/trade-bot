"""Orchestrates feature computation across multiple providers."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from src.ml.models import FeatureVector

if TYPE_CHECKING:
    from src.ml.feature_store import FeatureStore

logger = logging.getLogger(__name__)


class FeatureEngine:
    """Computes and stores features from all data sources."""

    def __init__(self, providers: list, store: FeatureStore) -> None:
        self._providers = providers
        self._store = store

    async def compute_and_store(
        self, symbol: str, raw_data: dict[str, Any], timestamp: int
    ) -> FeatureVector:
        """Run all feature providers in parallel and persist results."""
        all_features: dict[str, float] = {}

        tasks = [p.compute(raw_data) for p in self._providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for provider, result in zip(self._providers, results, strict=False):
            if isinstance(result, Exception):
                logger.warning("Feature provider %s failed: %s", provider.name, result)
                continue
            all_features.update(result)

        self._store.save(symbol, timestamp, all_features)

        return FeatureVector(symbol=symbol, timestamp=timestamp, features=all_features)

    async def get_vector(self, symbol: str, timestamp: int) -> FeatureVector:
        """Retrieve a stored feature vector."""
        features = self._store.load(symbol, timestamp)
        return FeatureVector(symbol=symbol, timestamp=timestamp, features=features)
