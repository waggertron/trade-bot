"""Tests for wiring MLEnsembleStrategy into the strategies list."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.config import Settings
from src.core.models import AssetType, MarketTick, SignalDirection
from src.ml.feature_store import FeatureStore
from src.ml.mock_model import MockModel
from src.ml.models import FeatureVector


def test_build_ml_strategy_mock_true():
    """When use_mocks.ml=True, builds MLEnsembleStrategy with MockModel."""
    from main import build_ml_strategy

    settings = Settings.for_testing(use_mocks={"ml": True})
    strategy = build_ml_strategy(settings)
    assert strategy is not None
    assert isinstance(strategy._model, MockModel)


def test_build_ml_strategy_mock_false():
    """When use_mocks.ml=False, builds MLEnsembleStrategy with EnsembleModel."""
    from main import build_ml_strategy
    from src.ml.ensemble import EnsembleModel

    settings = Settings.for_testing(use_mocks={"ml": False})
    strategy = build_ml_strategy(settings)
    assert isinstance(strategy._model, EnsembleModel)


@pytest.mark.asyncio
async def test_ml_tick_adapter_bridges_to_feature_strategy():
    """MLTickAdapter bridges the tick-based evaluate to feature-based evaluate."""
    from main import MLTickAdapter

    model = MockModel(default_direction="buy", default_confidence=0.8)
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy
    ml_strategy = MLEnsembleStrategy(model=model)

    feature_store = FeatureStore()
    # Pre-populate store with a feature vector
    feature_store.save("BTC/USD", 1000, {"sma_14": 50000.0, "rsi": 45.0})

    adapter = MLTickAdapter(ml_strategy, feature_store)
    assert adapter.name == "ml_ensemble"

    tick = MarketTick(
        symbol="BTC/USD",
        price=Decimal("50000"),
        volume=1000,
        timestamp=datetime.fromtimestamp(1000, tz=timezone.utc),
        asset_type=AssetType.CRYPTO,
    )

    # Call with the tick-based signature
    signal = await adapter.evaluate("BTC/USD", [tick], research=None)
    assert signal is not None
    assert signal.direction == SignalDirection.BUY
    assert signal.confidence == 0.8


@pytest.mark.asyncio
async def test_ml_tick_adapter_returns_none_when_no_features():
    """When no features exist in store, adapter returns None."""
    from main import MLTickAdapter

    model = MockModel(default_direction="buy", default_confidence=0.8)
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy
    ml_strategy = MLEnsembleStrategy(model=model)

    feature_store = FeatureStore()  # Empty store

    adapter = MLTickAdapter(ml_strategy, feature_store)

    tick = MarketTick(
        symbol="BTC/USD",
        price=Decimal("50000"),
        volume=1000,
        timestamp=datetime.fromtimestamp(2000, tz=timezone.utc),
        asset_type=AssetType.CRYPTO,
    )

    signal = await adapter.evaluate("BTC/USD", [tick], research=None)
    assert signal is None
