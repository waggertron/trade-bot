"""Tests for CrossAssetStrategy."""

from __future__ import annotations

import pytest

from src.agents.strategies.cross_asset import CrossAssetStrategy
from src.core.models import Signal, SignalDirection
from src.core.protocols import FeatureStrategy
from src.ml.models import FeatureVector

# -- Helper ---------------------------------------------------------------


def make_features(symbol: str = "ETH/USD", **feats: float) -> FeatureVector:
    return FeatureVector(symbol=symbol, timestamp=1_000_000, features=feats)


# ==========================================================================
# CrossAssetStrategy
# ==========================================================================


class TestCrossAssetStrategy:
    def test_is_instance_of_feature_strategy(self) -> None:
        strategy = CrossAssetStrategy()
        assert isinstance(strategy, FeatureStrategy)

    def test_name_property(self) -> None:
        strategy = CrossAssetStrategy()
        assert strategy.name == "cross_asset"

    def test_required_features(self) -> None:
        strategy = CrossAssetStrategy()
        assert strategy.required_features() == [
            "btc_momentum_lead",
            "btc_eth_corr_30d",
            "sma_5",
            "sma_14",
        ]

    async def test_buy_when_leader_bullish_and_asset_lagging(self) -> None:
        strategy = CrossAssetStrategy()
        fv = make_features(
            btc_momentum_lead=0.5,
            btc_eth_corr_30d=0.8,
            sma_5=95.0,
            sma_14=100.0,
        )
        result = await strategy.evaluate("ETH/USD", fv)
        assert result is not None
        assert isinstance(result, Signal)
        assert result.direction == SignalDirection.BUY
        assert result.symbol == "ETH/USD"
        assert result.strategy_name == "cross_asset"
        assert result.confidence > 0.0
        assert "Leader BTC/USD bullish" in result.reasoning
        assert "ETH/USD lagging" in result.reasoning

    async def test_no_signal_untracked_symbol(self) -> None:
        strategy = CrossAssetStrategy()
        fv = make_features(
            symbol="DOGE/USD",
            btc_momentum_lead=0.5,
            btc_eth_corr_30d=0.8,
            sma_5=95.0,
            sma_14=100.0,
        )
        result = await strategy.evaluate("DOGE/USD", fv)
        assert result is None

    async def test_no_signal_low_correlation(self) -> None:
        strategy = CrossAssetStrategy()
        fv = make_features(
            btc_momentum_lead=0.5,
            btc_eth_corr_30d=0.3,  # below min_correlation=0.6
            sma_5=95.0,
            sma_14=100.0,
        )
        result = await strategy.evaluate("ETH/USD", fv)
        assert result is None

    async def test_no_signal_asset_already_trending(self) -> None:
        strategy = CrossAssetStrategy()
        fv = make_features(
            btc_momentum_lead=0.5,
            btc_eth_corr_30d=0.8,
            sma_5=105.0,  # already trending up (sma_5 > sma_14)
            sma_14=100.0,
        )
        result = await strategy.evaluate("ETH/USD", fv)
        assert result is None

    async def test_no_signal_leader_bearish(self) -> None:
        strategy = CrossAssetStrategy()
        fv = make_features(
            btc_momentum_lead=-0.3,  # leader bearish
            btc_eth_corr_30d=0.8,
            sma_5=95.0,
            sma_14=100.0,
        )
        result = await strategy.evaluate("ETH/USD", fv)
        assert result is None

    async def test_custom_pairs(self) -> None:
        custom_pairs = {"LINK/USD": "ETH/USD"}
        strategy = CrossAssetStrategy(leader_pairs=custom_pairs)
        fv = make_features(
            symbol="LINK/USD",
            btc_momentum_lead=0.5,
            btc_eth_corr_30d=0.8,
            sma_5=95.0,
            sma_14=100.0,
        )
        result = await strategy.evaluate("LINK/USD", fv)
        assert result is not None
        assert result.direction == SignalDirection.BUY
        assert "Leader ETH/USD bullish" in result.reasoning
        assert "LINK/USD lagging" in result.reasoning

    async def test_confidence_calculation(self) -> None:
        strategy = CrossAssetStrategy()
        fv = make_features(
            btc_momentum_lead=0.5,
            btc_eth_corr_30d=0.8,
            sma_5=95.0,
            sma_14=100.0,
        )
        result = await strategy.evaluate("ETH/USD", fv)
        assert result is not None
        # confidence = min(abs(0.5) * abs(0.8), 1.0) = min(0.4, 1.0) = 0.4
        assert result.confidence == pytest.approx(0.4)

    async def test_confidence_capped_at_1(self) -> None:
        strategy = CrossAssetStrategy()
        fv = make_features(
            btc_momentum_lead=5.0,  # extreme momentum
            btc_eth_corr_30d=0.99,  # high correlation
            sma_5=50.0,
            sma_14=100.0,
        )
        result = await strategy.evaluate("ETH/USD", fv)
        assert result is not None
        # confidence = min(abs(5.0) * abs(0.99), 1.0) = min(4.95, 1.0) = 1.0
        assert result.confidence == pytest.approx(1.0)
