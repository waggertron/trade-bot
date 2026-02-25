"""Tests for EventDrivenStrategy."""

from __future__ import annotations

import pytest

from src.agents.strategies.event_driven import EventDrivenStrategy
from src.core.models import Signal, SignalDirection
from src.core.protocols import FeatureStrategy
from src.ml.models import FeatureVector

# -- Helper ---------------------------------------------------------------


def make_features(symbol: str = "BTC/USD", **feats: float) -> FeatureVector:
    return FeatureVector(symbol=symbol, timestamp=1_000_000, features=feats)


# ==========================================================================
# EventDrivenStrategy
# ==========================================================================


class TestEventDrivenStrategy:
    def test_is_instance_of_feature_strategy(self) -> None:
        strategy = EventDrivenStrategy()
        assert isinstance(strategy, FeatureStrategy)

    def test_name_property(self) -> None:
        strategy = EventDrivenStrategy()
        assert strategy.name == "event_driven"

    def test_required_features(self) -> None:
        strategy = EventDrivenStrategy()
        assert strategy.required_features() == [
            "article_volume_ratio",
            "sentiment_avg_6h",
            "sentiment_velocity",
        ]

    async def test_buy_on_positive_sentiment_spike(self) -> None:
        strategy = EventDrivenStrategy()
        fv = make_features(
            article_volume_ratio=4.0,
            sentiment_avg_6h=0.7,
            sentiment_velocity=0.5,
        )
        result = await strategy.evaluate("BTC/USD", fv)
        assert result is not None
        assert isinstance(result, Signal)
        assert result.direction == SignalDirection.BUY
        assert result.symbol == "BTC/USD"
        assert result.strategy_name == "event_driven"
        assert result.confidence > 0.0
        assert "Sentiment spike" in result.reasoning

    async def test_sell_on_negative_sentiment_spike(self) -> None:
        strategy = EventDrivenStrategy()
        fv = make_features(
            article_volume_ratio=5.0,
            sentiment_avg_6h=-0.8,
            sentiment_velocity=-0.3,
        )
        result = await strategy.evaluate("BTC/USD", fv)
        assert result is not None
        assert isinstance(result, Signal)
        assert result.direction == SignalDirection.SELL
        assert result.symbol == "BTC/USD"
        assert result.strategy_name == "event_driven"
        assert result.confidence > 0.0

    async def test_no_signal_below_volume_threshold(self) -> None:
        strategy = EventDrivenStrategy()
        # vol_ratio=2.0 is below default threshold of 3.0
        fv = make_features(
            article_volume_ratio=2.0,
            sentiment_avg_6h=0.7,
            sentiment_velocity=0.5,
        )
        result = await strategy.evaluate("BTC/USD", fv)
        assert result is None

    async def test_no_signal_below_sentiment_threshold(self) -> None:
        strategy = EventDrivenStrategy()
        # sentiment=0.3 is below default threshold of 0.5
        fv = make_features(
            article_volume_ratio=4.0,
            sentiment_avg_6h=0.3,
            sentiment_velocity=0.1,
        )
        result = await strategy.evaluate("BTC/USD", fv)
        assert result is None

    async def test_confidence_calculation(self) -> None:
        strategy = EventDrivenStrategy(volume_spike_threshold=3.0)
        fv = make_features(
            article_volume_ratio=4.0,
            sentiment_avg_6h=0.7,
            sentiment_velocity=0.5,
        )
        result = await strategy.evaluate("BTC/USD", fv)
        assert result is not None
        # confidence = min((4.0 / 3.0) * abs(0.7), 1.0)
        #            = min(1.3333... * 0.7, 1.0)
        #            = min(0.9333..., 1.0)
        #            = 0.9333...
        expected = (4.0 / 3.0) * 0.7
        assert result.confidence == pytest.approx(expected)

    async def test_confidence_capped_at_1(self) -> None:
        strategy = EventDrivenStrategy(volume_spike_threshold=3.0)
        # Extreme values that would push confidence > 1.0
        fv = make_features(
            article_volume_ratio=10.0,
            sentiment_avg_6h=0.9,
            sentiment_velocity=1.0,
        )
        result = await strategy.evaluate("BTC/USD", fv)
        assert result is not None
        assert result.confidence == pytest.approx(1.0)

    async def test_default_feature_values(self) -> None:
        strategy = EventDrivenStrategy()
        # No features in vector -> defaults apply
        # vol_ratio defaults to 1.0 which is < 3.0 -> None
        fv = make_features()
        result = await strategy.evaluate("BTC/USD", fv)
        assert result is None
