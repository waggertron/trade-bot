"""Tests for strategy adapters (Momentum, Sentiment, Quantitative)."""

from __future__ import annotations

import pytest

from src.agents.strategies.adapters import (
    MomentumAdapter,
    QuantitativeAdapter,
    SentimentAdapter,
)
from src.core.models import Signal, SignalDirection
from src.core.protocols import FeatureStrategy
from src.ml.models import FeatureVector


# -- Helper ---------------------------------------------------------------


def make_features(symbol: str = "BTC/USD", **feats: float) -> FeatureVector:
    return FeatureVector(symbol=symbol, timestamp=1_000_000, features=feats)


# ==========================================================================
# MomentumAdapter
# ==========================================================================


class TestMomentumAdapter:
    def test_is_instance_of_feature_strategy(self) -> None:
        adapter = MomentumAdapter()
        assert isinstance(adapter, FeatureStrategy)

    def test_name_property(self) -> None:
        adapter = MomentumAdapter()
        assert adapter.name == "momentum"

    def test_required_features(self) -> None:
        adapter = MomentumAdapter()
        assert adapter.required_features() == ["sma_5", "sma_14"]

    async def test_buy_signal(self) -> None:
        adapter = MomentumAdapter()
        fv = make_features(sma_5=110.0, sma_14=100.0)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert isinstance(result, Signal)
        assert result.direction == SignalDirection.BUY
        assert result.symbol == "BTC/USD"
        assert result.strategy_name == "momentum"
        assert result.confidence > 0.0
        assert "SMA5" in result.reasoning
        assert "SMA14" in result.reasoning

    async def test_sell_signal(self) -> None:
        adapter = MomentumAdapter()
        fv = make_features(sma_5=90.0, sma_14=100.0)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.direction == SignalDirection.SELL
        assert result.confidence > 0.0

    async def test_no_signal_missing_feature(self) -> None:
        adapter = MomentumAdapter()
        # Only sma_5 provided, sma_14 is missing
        fv = make_features(sma_5=110.0)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is None

    async def test_no_signal_neutral(self) -> None:
        adapter = MomentumAdapter()
        # Equal SMAs -> no signal
        fv = make_features(sma_5=100.0, sma_14=100.0)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is None

    async def test_confidence_capped(self) -> None:
        adapter = MomentumAdapter()
        # Huge divergence -> confidence should still be capped at 1.0
        fv = make_features(sma_5=500.0, sma_14=100.0)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.confidence <= 1.0

    async def test_no_signal_sma14_zero(self) -> None:
        adapter = MomentumAdapter()
        fv = make_features(sma_5=100.0, sma_14=0.0)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is None


# ==========================================================================
# SentimentAdapter
# ==========================================================================


class TestSentimentAdapter:
    def test_is_instance_of_feature_strategy(self) -> None:
        adapter = SentimentAdapter()
        assert isinstance(adapter, FeatureStrategy)

    def test_name_property(self) -> None:
        adapter = SentimentAdapter()
        assert adapter.name == "sentiment"

    def test_required_features(self) -> None:
        adapter = SentimentAdapter()
        assert adapter.required_features() == ["sentiment_avg_6h"]

    async def test_buy_signal(self) -> None:
        adapter = SentimentAdapter()
        fv = make_features(sentiment_avg_6h=0.8)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert isinstance(result, Signal)
        assert result.direction == SignalDirection.BUY
        assert result.symbol == "BTC/USD"
        assert result.strategy_name == "sentiment"
        assert result.confidence == pytest.approx(0.8)

    async def test_sell_signal(self) -> None:
        adapter = SentimentAdapter()
        fv = make_features(sentiment_avg_6h=-0.7)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.direction == SignalDirection.SELL
        assert result.confidence == pytest.approx(0.7)

    async def test_no_signal_missing_feature(self) -> None:
        adapter = SentimentAdapter()
        fv = make_features()  # no sentiment feature
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is None

    async def test_no_signal_neutral(self) -> None:
        adapter = SentimentAdapter()
        # Sentiment within neutral zone
        fv = make_features(sentiment_avg_6h=0.3)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is None

    async def test_confidence_capped(self) -> None:
        adapter = SentimentAdapter()
        # Extreme sentiment value
        fv = make_features(sentiment_avg_6h=5.0)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.confidence <= 1.0

    async def test_custom_thresholds(self) -> None:
        adapter = SentimentAdapter(buy_threshold=0.3, sell_threshold=-0.3)
        fv = make_features(sentiment_avg_6h=0.4)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.direction == SignalDirection.BUY

    async def test_buy_at_exact_threshold(self) -> None:
        adapter = SentimentAdapter(buy_threshold=0.6)
        fv = make_features(sentiment_avg_6h=0.6)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.direction == SignalDirection.BUY

    async def test_sell_at_exact_threshold(self) -> None:
        adapter = SentimentAdapter(sell_threshold=-0.6)
        fv = make_features(sentiment_avg_6h=-0.6)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.direction == SignalDirection.SELL


# ==========================================================================
# QuantitativeAdapter
# ==========================================================================


class TestQuantitativeAdapter:
    def test_is_instance_of_feature_strategy(self) -> None:
        adapter = QuantitativeAdapter()
        assert isinstance(adapter, FeatureStrategy)

    def test_name_property(self) -> None:
        adapter = QuantitativeAdapter()
        assert adapter.name == "quantitative"

    def test_required_features(self) -> None:
        adapter = QuantitativeAdapter()
        assert adapter.required_features() == ["price_zscore"]

    async def test_buy_signal(self) -> None:
        adapter = QuantitativeAdapter()
        # zscore <= -2.0 -> mean reversion BUY
        fv = make_features(price_zscore=-2.5)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert isinstance(result, Signal)
        assert result.direction == SignalDirection.BUY
        assert result.symbol == "BTC/USD"
        assert result.strategy_name == "quantitative"
        assert result.confidence > 0.0

    async def test_sell_signal(self) -> None:
        adapter = QuantitativeAdapter()
        # zscore >= 2.0 -> SELL
        fv = make_features(price_zscore=2.5)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.direction == SignalDirection.SELL
        assert result.confidence > 0.0

    async def test_no_signal_missing_feature(self) -> None:
        adapter = QuantitativeAdapter()
        fv = make_features()
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is None

    async def test_no_signal_neutral(self) -> None:
        adapter = QuantitativeAdapter()
        # zscore within threshold -> no signal
        fv = make_features(price_zscore=0.5)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is None

    async def test_confidence_capped(self) -> None:
        adapter = QuantitativeAdapter()
        # Extreme z-score
        fv = make_features(price_zscore=-10.0)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.confidence <= 1.0

    async def test_custom_z_threshold(self) -> None:
        adapter = QuantitativeAdapter(z_threshold=1.0)
        fv = make_features(price_zscore=-1.5)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.direction == SignalDirection.BUY

    async def test_buy_at_exact_threshold(self) -> None:
        adapter = QuantitativeAdapter(z_threshold=2.0)
        fv = make_features(price_zscore=-2.0)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.direction == SignalDirection.BUY

    async def test_sell_at_exact_threshold(self) -> None:
        adapter = QuantitativeAdapter(z_threshold=2.0)
        fv = make_features(price_zscore=2.0)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.direction == SignalDirection.SELL

    async def test_confidence_formula(self) -> None:
        adapter = QuantitativeAdapter(z_threshold=2.0)
        fv = make_features(price_zscore=-3.0)
        result = await adapter.evaluate("BTC/USD", fv)
        assert result is not None
        # confidence = min(abs(-3.0) / (2.0 * 2), 1.0) = min(0.75, 1.0) = 0.75
        assert result.confidence == pytest.approx(0.75)
