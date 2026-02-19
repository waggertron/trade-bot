"""Tests for wiring FeatureStore and FeatureEngine in main.py."""

from __future__ import annotations

import pytest

from src.core.config import Settings
from src.ml.feature_engine import FeatureEngine
from src.ml.feature_store import FeatureStore
from src.providers.mock import MockFeatureProvider


def test_build_feature_engine_mock_true():
    """When use_mocks.ml=True, build_feature_engine uses MockFeatureProvider."""
    from main import build_feature_engine

    settings = Settings.for_testing(use_mocks={"ml": True})
    engine, store = build_feature_engine(settings)
    assert isinstance(engine, FeatureEngine)
    assert isinstance(store, FeatureStore)
    assert len(engine._providers) >= 1
    assert any(isinstance(p, MockFeatureProvider) for p in engine._providers)


def test_build_feature_engine_mock_false():
    """When use_mocks.ml=False, build_feature_engine uses TechnicalFeatureProvider."""
    from main import build_feature_engine
    from src.providers.technical import TechnicalFeatureProvider

    settings = Settings.for_testing(use_mocks={"ml": False})
    engine, store = build_feature_engine(settings)
    assert isinstance(engine, FeatureEngine)
    assert any(isinstance(p, TechnicalFeatureProvider) for p in engine._providers)


@pytest.mark.asyncio
async def test_feature_engine_compute_and_store_works():
    """End-to-end: FeatureEngine with MockFeatureProvider can compute and store."""
    store = FeatureStore()
    provider = MockFeatureProvider()
    engine = FeatureEngine(providers=[provider], store=store)

    vector = await engine.compute_and_store(
        symbol="BTC/USD",
        raw_data={"price": 50000, "volume": 1000},
        timestamp=1000,
    )

    assert vector.symbol == "BTC/USD"
    assert vector.timestamp == 1000
    assert store.count() == 1
