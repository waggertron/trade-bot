"""Tests for the FeatureStrategy protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.protocols import FeatureStrategy, StrategyAgent

if TYPE_CHECKING:
    from src.core.models import Signal
    from src.ml.models import FeatureVector

# -- Dummy classes for protocol conformance testing -----------------------


class _ConformingStrategy:
    """A dummy class that implements all FeatureStrategy requirements."""

    name: str = "test-strategy"

    async def evaluate(self, symbol: str, features: FeatureVector) -> Signal | None:
        return None

    def required_features(self) -> list[str]:
        return ["rsi", "macd"]


class _NonConformingStrategy:
    """A dummy class that is missing required_features."""

    name: str = "bad-strategy"

    async def evaluate(self, symbol: str, features: FeatureVector) -> Signal | None:
        return None


# -- Tests ----------------------------------------------------------------


def test_feature_strategy_is_runtime_checkable() -> None:
    """FeatureStrategy should be a runtime-checkable Protocol."""

    # It should be a Protocol (has _is_protocol attribute)
    assert getattr(FeatureStrategy, "_is_protocol", False) is True
    # Verify isinstance checks work (runtime_checkable)
    assert isinstance(_ConformingStrategy(), FeatureStrategy)


def test_conforming_class_passes_isinstance() -> None:
    """A class with name, evaluate, and required_features passes isinstance."""
    strategy = _ConformingStrategy()
    assert isinstance(strategy, FeatureStrategy)


def test_nonconforming_class_fails() -> None:
    """A class missing required_features fails isinstance check."""
    strategy = _NonConformingStrategy()
    assert not isinstance(strategy, FeatureStrategy)


def test_protocol_exists_alongside_strategy_agent() -> None:
    """Both StrategyAgent and FeatureStrategy should coexist in protocols module."""
    import src.core.protocols as protocols_mod

    assert hasattr(protocols_mod, "StrategyAgent")
    assert hasattr(protocols_mod, "FeatureStrategy")
    # They should be distinct protocols
    assert StrategyAgent is not FeatureStrategy
