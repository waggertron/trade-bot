"""Tests verifying MLEnsembleStrategy works with EnsembleModel."""
from __future__ import annotations

import pytest

from src.agents.strategies.ml_ensemble import MLEnsembleStrategy
from src.ml.ensemble import EnsembleModel
from src.ml.mock_model import MockModel
from src.ml.models import FeatureVector


def _make_fv() -> FeatureVector:
    return FeatureVector(symbol="BTC/USD", timestamp=1700000000, features={"rsi": 55.0})


class TestMLEnsembleWithEnsembleModel:
    @pytest.mark.asyncio
    async def test_produces_signal_from_ensemble(self):
        """EnsembleModel wrapping two bullish MockModels produces a BUY signal."""
        m1 = MockModel(default_direction="buy", default_confidence=0.8)
        m2 = MockModel(default_direction="buy", default_confidence=0.7)
        ensemble = EnsembleModel(models=[m1, m2])
        strategy = MLEnsembleStrategy(model=ensemble, min_confidence=0.5)

        signal = await strategy.evaluate("BTC/USD", _make_fv())
        assert signal is not None
        assert signal.direction.value == "buy"

    @pytest.mark.asyncio
    async def test_filters_hold_from_ensemble(self):
        """EnsembleModel returning hold is filtered by strategy."""
        m1 = MockModel(default_direction="hold", default_confidence=0.5)
        ensemble = EnsembleModel(models=[m1])
        strategy = MLEnsembleStrategy(model=ensemble)

        signal = await strategy.evaluate("BTC/USD", _make_fv())
        assert signal is None

    @pytest.mark.asyncio
    async def test_filters_low_confidence_from_ensemble(self):
        """EnsembleModel returning low confidence is filtered."""
        m1 = MockModel(default_direction="buy", default_confidence=0.3)
        m2 = MockModel(default_direction="sell", default_confidence=0.25)
        ensemble = EnsembleModel(models=[m1, m2])
        strategy = MLEnsembleStrategy(model=ensemble, min_confidence=0.8)

        signal = await strategy.evaluate("BTC/USD", _make_fv())
        # Confidence from ensemble will be below 0.8
        assert signal is None
