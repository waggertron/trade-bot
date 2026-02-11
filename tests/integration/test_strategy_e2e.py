"""End-to-end integration tests for the full strategy pipeline."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.agents.strategies.adapters import (
    MomentumAdapter,
    QuantitativeAdapter,
    SentimentAdapter,
)
from src.agents.strategies.consensus import WeightedConsensus
from src.agents.strategies.cross_asset import CrossAssetStrategy
from src.agents.strategies.event_driven import EventDrivenStrategy
from src.agents.strategies.ml_ensemble import MLEnsembleStrategy
from src.core.models import (
    PortfolioSnapshot,
    Signal,
    SignalDirection,
)
from src.ml.mock_model import MockModel
from src.ml.models import FeatureVector
from src.risk.models import RiskContext, StrategyPerformance, VolatilityRegime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signal(
    symbol: str = "BTC/USD",
    direction: SignalDirection = SignalDirection.BUY,
    confidence: float = 0.7,
    strategy: str = "momentum",
) -> Signal:
    return Signal(
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        strategy_name=strategy,
        reasoning="Test signal",
        timestamp=datetime.now(timezone.utc),
    )


def _make_portfolio(
    cash: Decimal = Decimal("50000"),
) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        cash=cash,
        positions=[],
        timestamp=datetime(2025, 6, 1, 12, 0, 0),
    )


def _make_risk_context(
    regime: VolatilityRegime = VolatilityRegime.MEDIUM,
    strategy_stats: dict[str, StrategyPerformance] | None = None,
) -> RiskContext:
    return RiskContext(
        regime=regime,
        correlation_matrix={},
        strategy_stats=strategy_stats or {},
        drawdown_from_peak=0.0,
        portfolio=_make_portfolio(),
        daily_pnl=Decimal("0"),
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestStrategyPipelineE2E:
    """Full integration: strategies + adapters + consensus working together."""

    async def test_full_strategy_pipeline(self):
        """Happy path: multiple strategies agree on BUY, consensus returns BUY."""
        symbol = "BTC/USD"
        ts = int(time.time())

        features = FeatureVector(
            symbol=symbol,
            timestamp=ts,
            features={
                "sma_5": 105.0,
                "sma_14": 100.0,
                "sentiment_avg_6h": 0.7,
                "price_zscore": -2.5,
                "article_volume_ratio": 1.0,
                "sentiment_velocity": 0.1,
            },
        )

        # Set up all strategies
        momentum = MomentumAdapter()
        sentiment = SentimentAdapter()
        quantitative = QuantitativeAdapter()
        event_driven = EventDrivenStrategy()
        mock_model = MockModel(default_direction="buy", default_confidence=0.8)
        ml_ensemble = MLEnsembleStrategy(model=mock_model)

        strategies = [momentum, sentiment, quantitative, event_driven, ml_ensemble]

        # Run all strategies and collect non-None signals
        signals: list[Signal] = []
        for strategy in strategies:
            result = await strategy.evaluate(symbol, features)
            if result is not None:
                signals.append(result)

        # Momentum BUY (spread=5%, conf=0.5), Sentiment BUY (conf=0.7),
        # Quantitative BUY (zscore=-2.5, conf=0.625), ML BUY (conf=0.8)
        # EventDriven returns None (article_volume_ratio=1.0 < 3.0 threshold)
        assert len(signals) == 4, f"Expected 4 signals, got {len(signals)}"

        strategy_names = {s.strategy_name for s in signals}
        assert strategy_names == {"momentum", "sentiment", "quantitative", "ml_ensemble"}

        for sig in signals:
            assert sig.direction == SignalDirection.BUY

        # Resolve via WeightedConsensus
        consensus = WeightedConsensus()
        result = await consensus.resolve(signals)

        assert result is not None, "Consensus should return a signal"
        assert result.direction == SignalDirection.BUY

    async def test_weighted_consensus_with_risk_context(self):
        """Momentum BUY wins over sentiment SELL due to higher weight and win rate."""
        momentum_signal = _make_signal(
            direction=SignalDirection.BUY,
            confidence=0.7,
            strategy="momentum",
        )
        sentiment_signal = _make_signal(
            direction=SignalDirection.SELL,
            confidence=0.9,
            strategy="sentiment",
        )

        # Momentum: win_rate=0.8 with 10 trades (meets threshold)
        # Sentiment: win_rate=0.4 with 15 trades (meets threshold)
        risk_ctx = _make_risk_context(
            strategy_stats={
                "momentum": StrategyPerformance(
                    name="momentum",
                    win_rate=0.6,
                    avg_win=Decimal("200"),
                    avg_loss=Decimal("100"),
                    total_trades=20,
                    recent_trades=10,
                    recent_win_rate=0.8,
                ),
                "sentiment": StrategyPerformance(
                    name="sentiment",
                    win_rate=0.4,
                    avg_win=Decimal("100"),
                    avg_loss=Decimal("150"),
                    total_trades=30,
                    recent_trades=15,
                    recent_win_rate=0.4,
                ),
            },
        )

        consensus = WeightedConsensus(
            strategy_weights={"momentum": 0.6, "sentiment": 0.2},
        )

        # Weighted scores:
        #   momentum BUY: 0.7 * 0.6 * 0.8 * 1.0 = 0.336
        #   sentiment SELL: 0.9 * 0.2 * 0.4 * 1.0 = 0.072
        # BUY total = 0.336 > SELL total = 0.072 -> momentum BUY wins
        result = await consensus.resolve(
            [momentum_signal, sentiment_signal],
            risk_context=risk_ctx,
        )

        assert result is not None, "Expected a consensus signal"
        assert result.direction == SignalDirection.BUY
        assert result.strategy_name == "momentum"

    async def test_event_driven_triggers_on_spike(self):
        """Event-driven strategy fires BUY on article volume spike with positive sentiment."""
        symbol = "BTC/USD"
        ts = int(time.time())

        features = FeatureVector(
            symbol=symbol,
            timestamp=ts,
            features={
                "article_volume_ratio": 5.0,
                "sentiment_avg_6h": 0.8,
                "sentiment_velocity": 0.5,
            },
        )

        strategy = EventDrivenStrategy()
        result = await strategy.evaluate(symbol, features)

        assert result is not None, "Expected event-driven signal"
        assert result.direction == SignalDirection.BUY
        assert result.strategy_name == "event_driven"

        # confidence = min((5.0 / 3.0) * 0.8, 1.0) = min(1.333, 1.0) = 1.0
        assert result.confidence == pytest.approx(1.0)

    async def test_cross_asset_detects_lag(self):
        """Cross-asset strategy detects ETH lagging BTC and generates BUY."""
        symbol = "ETH/USD"
        ts = int(time.time())

        features = FeatureVector(
            symbol=symbol,
            timestamp=ts,
            features={
                "btc_momentum_lead": 0.5,
                "btc_eth_corr_30d": 0.8,
                "sma_5": 95.0,
                "sma_14": 100.0,
            },
        )

        strategy = CrossAssetStrategy()
        result = await strategy.evaluate(symbol, features)

        assert result is not None, "Expected cross-asset signal"
        assert result.direction == SignalDirection.BUY
        assert result.strategy_name == "cross_asset"

        # confidence = min(0.5 * 0.8, 1.0) = 0.4
        assert result.confidence == pytest.approx(0.4)
        assert "ETH/USD" in result.reasoning
        assert "BTC/USD" in result.reasoning

    async def test_no_consensus_below_threshold(self):
        """Very weak signals produce no consensus when min_consensus_score is high."""
        # Create weak signals with low confidence
        weak_buy = _make_signal(
            direction=SignalDirection.BUY,
            confidence=0.1,
            strategy="momentum",
        )
        weak_sell = _make_signal(
            direction=SignalDirection.SELL,
            confidence=0.1,
            strategy="sentiment",
        )

        # With default weights (1.0) and no risk context:
        #   accuracy_weight = 0.5 (default when no risk context)
        #   momentum BUY: 0.1 * 1.0 * 0.5 * 1.0 = 0.05
        #   sentiment SELL: 0.1 * 1.0 * 0.5 * 1.0 = 0.05
        # Both totals (0.05) are below min_consensus_score=0.5 -> returns None
        consensus = WeightedConsensus(min_consensus_score=0.5)
        result = await consensus.resolve([weak_buy, weak_sell])

        assert result is None, "Expected no consensus for weak signals"
