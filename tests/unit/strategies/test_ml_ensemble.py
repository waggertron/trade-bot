"""Tests for MLEnsembleStrategy."""

from __future__ import annotations

import pytest

from src.core.models import Signal, SignalDirection
from src.core.protocols import FeatureStrategy
from src.ml.mock_model import MockModel
from src.ml.models import FeatureVector


@pytest.fixture()
def features() -> FeatureVector:
    return FeatureVector(
        symbol="BTC/USD",
        timestamp=1_700_000_000,
        features={"rsi": 55.0, "macd": 0.3},
    )


# -- Tests ----------------------------------------------------------------


def test_is_instance_of_feature_strategy() -> None:
    """MLEnsembleStrategy satisfies the FeatureStrategy protocol."""
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy

    model = MockModel()
    strategy = MLEnsembleStrategy(model=model)
    assert isinstance(strategy, FeatureStrategy)


def test_name_property() -> None:
    """Strategy name should be 'ml_ensemble'."""
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy

    strategy = MLEnsembleStrategy(model=MockModel())
    assert strategy.name == "ml_ensemble"


def test_required_features_empty() -> None:
    """required_features should return an empty list (uses all available)."""
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy

    strategy = MLEnsembleStrategy(model=MockModel())
    assert strategy.required_features() == []


@pytest.mark.asyncio
async def test_buy_signal(features: FeatureVector) -> None:
    """Model predicting 'buy' with high confidence should return a BUY Signal."""
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy

    model = MockModel(default_direction="buy", default_confidence=0.8)
    strategy = MLEnsembleStrategy(model=model)
    result = await strategy.evaluate("BTC/USD", features)

    assert result is not None
    assert isinstance(result, Signal)
    assert result.direction == SignalDirection.BUY
    assert result.confidence == 0.8
    assert result.strategy_name == "ml_ensemble"
    assert result.symbol == "BTC/USD"


@pytest.mark.asyncio
async def test_sell_signal(features: FeatureVector) -> None:
    """Model predicting 'sell' with high confidence should return a SELL Signal."""
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy

    model = MockModel(default_direction="sell", default_confidence=0.7)
    strategy = MLEnsembleStrategy(model=model)
    result = await strategy.evaluate("ETH/USD", features)

    assert result is not None
    assert isinstance(result, Signal)
    assert result.direction == SignalDirection.SELL
    assert result.confidence == 0.7
    assert result.symbol == "ETH/USD"


@pytest.mark.asyncio
async def test_hold_returns_none(features: FeatureVector) -> None:
    """Model predicting 'hold' should return None (no trade)."""
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy

    model = MockModel(default_direction="hold", default_confidence=0.9)
    strategy = MLEnsembleStrategy(model=model)
    result = await strategy.evaluate("BTC/USD", features)

    assert result is None


@pytest.mark.asyncio
async def test_low_confidence_returns_none(features: FeatureVector) -> None:
    """Confidence below default threshold (0.55) should return None."""
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy

    model = MockModel(default_direction="buy", default_confidence=0.3)
    strategy = MLEnsembleStrategy(model=model)
    result = await strategy.evaluate("BTC/USD", features)

    assert result is None


@pytest.mark.asyncio
async def test_custom_min_confidence(features: FeatureVector) -> None:
    """Custom min_confidence=0.9 should reject confidence=0.8."""
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy

    model = MockModel(default_direction="buy", default_confidence=0.8)
    strategy = MLEnsembleStrategy(model=model, min_confidence=0.9)
    result = await strategy.evaluate("BTC/USD", features)

    assert result is None


@pytest.mark.asyncio
async def test_reasoning_contains_direction(features: FeatureVector) -> None:
    """The reasoning string should include the prediction direction."""
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy

    model = MockModel(default_direction="buy", default_confidence=0.8)
    strategy = MLEnsembleStrategy(model=model)
    result = await strategy.evaluate("BTC/USD", features)

    assert result is not None
    assert "buy" in result.reasoning
    assert "0.80" in result.reasoning


@pytest.mark.asyncio
async def test_calls_model_predict(features: FeatureVector) -> None:
    """Calling evaluate should invoke model.predict exactly once."""
    from src.agents.strategies.ml_ensemble import MLEnsembleStrategy

    model = MockModel(default_direction="buy", default_confidence=0.8)
    strategy = MLEnsembleStrategy(model=model)

    assert model.predict_count == 0
    await strategy.evaluate("BTC/USD", features)
    assert model.predict_count == 1
