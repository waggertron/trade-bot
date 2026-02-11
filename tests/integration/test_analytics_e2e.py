"""End-to-end integration tests for the analytics pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.analytics.attribution import StrategyAttribution
from src.analytics.models import AttributedFill, Trade
from src.analytics.monte_carlo import MonteCarloSimulator
from src.analytics.regime_tagger import RegimeTagger
from src.analytics.reporter import AnalyticsReporter
from src.core.models import Fill, OrderSide


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COUNTER = 0


def _next_id() -> str:
    """Generate a unique fill id for test reproducibility."""
    global _COUNTER  # noqa: PLW0603
    _COUNTER += 1
    return f"fill-{_COUNTER}"


def _ts(minute: int) -> datetime:
    """Create a deterministic UTC timestamp at a given minute offset."""
    return datetime(2025, 6, 15, 12, minute, 0, tzinfo=timezone.utc)


def _make_fill(
    symbol: str,
    side: OrderSide,
    price: float,
    qty: float,
    minute: int,
    fill_id: str | None = None,
) -> Fill:
    return Fill(
        id=fill_id or _next_id(),
        order_id=f"ord-{_COUNTER}",
        symbol=symbol,
        side=side,
        quantity=Decimal(str(qty)),
        fill_price=Decimal(str(price)),
        timestamp=_ts(minute),
    )


def _make_attributed_fill(
    symbol: str,
    side: OrderSide,
    price: float,
    qty: float,
    strategy: str,
    regime: str,
    minute: int,
) -> AttributedFill:
    fill = _make_fill(symbol, side, price, qty, minute)
    return AttributedFill(fill=fill, strategy=strategy, regime=regime)


# ---------------------------------------------------------------------------
# Shared fill data for the "default" trading session
# ---------------------------------------------------------------------------


def _default_attributed_fills() -> list[AttributedFill]:
    """Simulate fills from a trading session with two strategies.

    Momentum (BTC/USD):
        BUY  50000 * 0.1 -> SELL 52000 * 0.1  =>  pnl = +200
        BUY  53000 * 0.1 -> SELL 51000 * 0.1  =>  pnl = -200
        Net = 0.0, win_rate = 0.5

    ML Ensemble (ETH/USD):
        BUY  3000  * 1.0 -> SELL 3200  * 1.0  =>  pnl = +200
        BUY  3100  * 1.0 -> SELL 3300  * 1.0  =>  pnl = +200
        Net = +400, win_rate = 1.0
    """
    fills_data: list[tuple[str, OrderSide, float, float, str, str, int]] = [
        # (symbol, side, price, qty, strategy, regime, minute)
        ("BTC/USD", OrderSide.BUY, 50000, 0.1, "momentum", "medium", 0),
        ("BTC/USD", OrderSide.SELL, 52000, 0.1, "momentum", "medium", 1),
        ("BTC/USD", OrderSide.BUY, 53000, 0.1, "momentum", "high", 2),
        ("BTC/USD", OrderSide.SELL, 51000, 0.1, "momentum", "high", 3),
        ("ETH/USD", OrderSide.BUY, 3000, 1.0, "ml_ensemble", "low", 4),
        ("ETH/USD", OrderSide.SELL, 3200, 1.0, "ml_ensemble", "low", 5),
        ("ETH/USD", OrderSide.BUY, 3100, 1.0, "ml_ensemble", "medium", 6),
        ("ETH/USD", OrderSide.SELL, 3300, 1.0, "ml_ensemble", "medium", 7),
    ]
    return [
        _make_attributed_fill(sym, side, price, qty, strat, regime, minute)
        for sym, side, price, qty, strat, regime, minute in fills_data
    ]


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestFullAnalyticsPipeline:
    """Happy path: attribution + monte carlo + reporter in one pass."""

    def test_full_analytics_pipeline(self) -> None:
        fills = _default_attributed_fills()

        # --- 1. Attribution ---
        attribution = StrategyAttribution()
        report = attribution.analyze(fills)

        assert len(report.strategies) == 2
        assert "momentum" in report.strategies
        assert "ml_ensemble" in report.strategies

        momentum_stats = report.strategies["momentum"]
        ml_stats = report.strategies["ml_ensemble"]

        # Momentum: +200 - 200 = 0
        assert momentum_stats.total_pnl == pytest.approx(0.0)
        assert momentum_stats.total_trades == 2
        assert momentum_stats.win_rate == pytest.approx(0.5)

        # ML Ensemble: +200 + 200 = 400
        assert ml_stats.total_pnl == pytest.approx(400.0)
        assert ml_stats.total_trades == 2
        assert ml_stats.win_rate == pytest.approx(1.0)

        # Overall
        assert report.total_pnl == pytest.approx(400.0)

        # --- 2. Monte Carlo ---
        trades = [
            Trade(
                symbol="BTC/USD",
                entry_price=50000,
                exit_price=52000,
                quantity=0.1,
                pnl=200.0,
                strategy="momentum",
            ),
            Trade(
                symbol="BTC/USD",
                entry_price=53000,
                exit_price=51000,
                quantity=0.1,
                pnl=-200.0,
                strategy="momentum",
            ),
            Trade(
                symbol="ETH/USD",
                entry_price=3000,
                exit_price=3200,
                quantity=1.0,
                pnl=200.0,
                strategy="ml_ensemble",
            ),
            Trade(
                symbol="ETH/USD",
                entry_price=3100,
                exit_price=3300,
                quantity=1.0,
                pnl=200.0,
                strategy="ml_ensemble",
            ),
        ]

        simulator = MonteCarloSimulator(n_simulations=100, seed=42)
        mc_result = simulator.simulate(trades, initial_cash=10000.0)

        assert mc_result.n_simulations == 100
        assert 0.0 <= mc_result.percentile <= 100.0
        assert mc_result.actual_final_value == pytest.approx(10400.0)
        assert mc_result.median_simulated > 0.0
        assert mc_result.p5_simulated <= mc_result.p95_simulated

        # --- 3. Reporter ---
        reporter = AnalyticsReporter(
            attribution=attribution,
            simulator=MonteCarloSimulator(n_simulations=50, seed=42),
        )
        text = reporter.generate_report(fills, initial_cash=10000.0)

        assert len(text) > 0
        assert "ANALYTICS REPORT" in text
        assert "STRATEGY BREAKDOWN" in text
        assert "MONTE CARLO ANALYSIS" in text


class TestRegimeTaggerPipeline:
    """Regime tagging: raw fills are tagged and per-regime stats are computed."""

    def test_regime_tagger_pipeline(self) -> None:
        # --- Set up regime tagger ---
        tagger = RegimeTagger()

        # Create raw fills (not yet attributed) with known timestamps
        raw_fills: list[Fill] = []
        strategy_map: dict[str, str] = {}

        # Momentum trades in "high" regime
        ts_high = _ts(10)
        ts_high_unix = int(ts_high.timestamp())
        tagger.set_regime("BTC/USD", ts_high_unix, "high")

        f1 = _make_fill("BTC/USD", OrderSide.BUY, 50000, 0.1, 10, fill_id="f1")
        f2 = _make_fill("BTC/USD", OrderSide.SELL, 52000, 0.1, 10, fill_id="f2")
        raw_fills.extend([f1, f2])
        strategy_map["f1"] = "momentum"
        strategy_map["f2"] = "momentum"

        # ML Ensemble trades in "low" regime
        ts_low = _ts(20)
        ts_low_unix = int(ts_low.timestamp())
        tagger.set_regime("ETH/USD", ts_low_unix, "low")

        f3 = _make_fill("ETH/USD", OrderSide.BUY, 3000, 1.0, 20, fill_id="f3")
        f4 = _make_fill("ETH/USD", OrderSide.SELL, 3200, 1.0, 20, fill_id="f4")
        raw_fills.extend([f3, f4])
        strategy_map["f3"] = "ml_ensemble"
        strategy_map["f4"] = "ml_ensemble"

        # --- Tag fills ---
        tagged = tagger.tag_fills(raw_fills, strategy_map=strategy_map)

        assert len(tagged) == 4

        # Verify BTC fills got "high" regime and "momentum" strategy
        btc_fills = [af for af in tagged if af.fill.symbol == "BTC/USD"]
        for af in btc_fills:
            assert af.regime == "high"
            assert af.strategy == "momentum"

        # Verify ETH fills got "low" regime and "ml_ensemble" strategy
        eth_fills = [af for af in tagged if af.fill.symbol == "ETH/USD"]
        for af in eth_fills:
            assert af.regime == "low"
            assert af.strategy == "ml_ensemble"

        # --- Per-regime performance ---
        regime_stats = tagger.performance_by_regime(tagged)

        assert "high" in regime_stats
        assert "low" in regime_stats

        # High regime: BTC buy 50000 sell 52000 -> pnl = +200
        high_stats = regime_stats["high"]
        assert high_stats.total_trades == 1
        assert high_stats.total_pnl == pytest.approx(200.0)

        # Low regime: ETH buy 3000 sell 3200 -> pnl = +200
        low_stats = regime_stats["low"]
        assert low_stats.total_trades == 1
        assert low_stats.total_pnl == pytest.approx(200.0)


class TestAttributionIdentifiesBestWorst:
    """Verify that attribution correctly identifies best/worst strategies."""

    def test_attribution_identifies_best_worst(self) -> None:
        # Momentum: net +200 (one winning trade)
        # ML Ensemble: net +400 (two winning trades)
        fills = [
            _make_attributed_fill("BTC/USD", OrderSide.BUY, 50000, 0.1, "momentum", "medium", 0),
            _make_attributed_fill("BTC/USD", OrderSide.SELL, 52000, 0.1, "momentum", "medium", 1),
            _make_attributed_fill("ETH/USD", OrderSide.BUY, 3000, 1.0, "ml_ensemble", "low", 2),
            _make_attributed_fill("ETH/USD", OrderSide.SELL, 3200, 1.0, "ml_ensemble", "low", 3),
            _make_attributed_fill("ETH/USD", OrderSide.BUY, 3100, 1.0, "ml_ensemble", "medium", 4),
            _make_attributed_fill("ETH/USD", OrderSide.SELL, 3300, 1.0, "ml_ensemble", "medium", 5),
        ]

        attribution = StrategyAttribution()
        report = attribution.analyze(fills)

        # momentum pnl = (52000-50000)*0.1 = +200
        # ml_ensemble pnl = (3200-3000)*1.0 + (3300-3100)*1.0 = +200 + +200 = +400
        assert report.best_strategy == "ml_ensemble"
        assert report.worst_strategy == "momentum"

        # Verify per-strategy stats
        momentum_stats = report.strategies["momentum"]
        assert momentum_stats.total_pnl == pytest.approx(200.0)
        assert momentum_stats.total_trades == 1
        assert momentum_stats.win_rate == pytest.approx(1.0)

        ml_stats = report.strategies["ml_ensemble"]
        assert ml_stats.total_pnl == pytest.approx(400.0)
        assert ml_stats.total_trades == 2
        assert ml_stats.win_rate == pytest.approx(1.0)


class TestReporterProducesCompleteReport:
    """Verify the reporter produces a complete, well-structured report."""

    def test_reporter_produces_complete_report(self) -> None:
        fills = _default_attributed_fills()

        attribution = StrategyAttribution()
        simulator = MonteCarloSimulator(n_simulations=100, seed=42)
        reporter = AnalyticsReporter(attribution=attribution, simulator=simulator)

        report = reporter.generate_report(fills, initial_cash=10000.0)

        # Verify section headers
        assert "ANALYTICS REPORT" in report
        assert "STRATEGY BREAKDOWN" in report
        assert "MONTE CARLO ANALYSIS" in report

        # Verify strategy names appear
        assert "momentum" in report
        assert "ml_ensemble" in report

        # Verify dollar amounts appear (P&L values)
        assert "$" in report

        # Verify the report contains percentage symbols (win rate, return)
        assert "%" in report

        # Verify simulations count is in the report
        assert "100 simulations" in report

        # Verify the report has content for each strategy
        assert "Win Rate" in report
        assert "Profit Factor" in report
        assert "Avg Win" in report
        assert "Avg Loss" in report
