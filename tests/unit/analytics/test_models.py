"""Tests for analytics models."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.analytics.models import (
    AttributedFill,
    AttributionReport,
    EquityPoint,
    MonteCarloResult,
    StrategyStats,
    Trade,
)
from src.core.models import Fill, OrderSide


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_fill() -> Fill:
    return Fill(
        order_id="order-1",
        symbol="BTC/USD",
        side=OrderSide.BUY,
        quantity=Decimal("1.5"),
        fill_price=Decimal("50000"),
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        commission=Decimal("10"),
    )


@pytest.fixture
def sample_attributed_fill(sample_fill: Fill) -> AttributedFill:
    return AttributedFill(
        fill=sample_fill,
        strategy="momentum",
        regime="high",
    )


@pytest.fixture
def sample_trade() -> Trade:
    return Trade(
        symbol="BTC/USD",
        entry_price=50000.0,
        exit_price=55000.0,
        quantity=1.5,
        pnl=7500.0,
        strategy="momentum",
        regime="high",
    )


@pytest.fixture
def sample_strategy_stats() -> StrategyStats:
    return StrategyStats(
        name="momentum",
        total_trades=100,
        win_rate=0.65,
        total_pnl=15000.0,
        avg_win=500.0,
        avg_loss=-200.0,
        profit_factor=2.5,
        max_consecutive_losses=5,
    )


@pytest.fixture
def sample_attribution_report(sample_strategy_stats: StrategyStats) -> AttributionReport:
    return AttributionReport(
        strategies={"momentum": sample_strategy_stats},
        total_pnl=15000.0,
        best_strategy="momentum",
        worst_strategy="momentum",
    )


@pytest.fixture
def sample_equity_point() -> EquityPoint:
    return EquityPoint(timestamp=1704067200, value=100000.0)


@pytest.fixture
def sample_monte_carlo_result() -> MonteCarloResult:
    return MonteCarloResult(
        actual_final_value=120000.0,
        percentile=75.0,
        median_simulated=110000.0,
        p5_simulated=90000.0,
        p95_simulated=140000.0,
        worst_drawdown_p95=0.25,
        n_simulations=10000,
    )


# ===========================================================================
# AttributedFill
# ===========================================================================


class TestAttributedFill:
    """Tests for the AttributedFill model."""

    def test_creation(self, sample_fill: Fill) -> None:
        af = AttributedFill(fill=sample_fill, strategy="momentum", regime="high")
        assert af.fill == sample_fill
        assert af.strategy == "momentum"
        assert af.regime == "high"

    def test_default_regime(self, sample_fill: Fill) -> None:
        af = AttributedFill(fill=sample_fill, strategy="mean_reversion")
        assert af.regime == "unknown"

    def test_frozen(self, sample_attributed_fill: AttributedFill) -> None:
        with pytest.raises(ValidationError):
            sample_attributed_fill.strategy = "other"  # type: ignore[misc]

    def test_requires_fill(self) -> None:
        with pytest.raises(ValidationError):
            AttributedFill(strategy="momentum")  # type: ignore[call-arg]

    def test_requires_strategy(self, sample_fill: Fill) -> None:
        with pytest.raises(ValidationError):
            AttributedFill(fill=sample_fill)  # type: ignore[call-arg]

    def test_serialization_roundtrip(self, sample_attributed_fill: AttributedFill) -> None:
        data = sample_attributed_fill.model_dump()
        restored = AttributedFill.model_validate(data)
        assert restored.strategy == sample_attributed_fill.strategy
        assert restored.regime == sample_attributed_fill.regime
        assert restored.fill.symbol == sample_attributed_fill.fill.symbol

    def test_json_roundtrip(self, sample_attributed_fill: AttributedFill) -> None:
        json_str = sample_attributed_fill.model_dump_json()
        restored = AttributedFill.model_validate_json(json_str)
        assert restored.strategy == sample_attributed_fill.strategy
        assert restored.fill.order_id == sample_attributed_fill.fill.order_id


# ===========================================================================
# Trade
# ===========================================================================


class TestTrade:
    """Tests for the Trade model."""

    def test_creation(self) -> None:
        t = Trade(
            symbol="ETH/USD",
            entry_price=3000.0,
            exit_price=3500.0,
            quantity=2.0,
            pnl=1000.0,
            strategy="breakout",
            regime="medium",
        )
        assert t.symbol == "ETH/USD"
        assert t.entry_price == 3000.0
        assert t.exit_price == 3500.0
        assert t.quantity == 2.0
        assert t.pnl == 1000.0
        assert t.strategy == "breakout"
        assert t.regime == "medium"

    def test_defaults(self) -> None:
        t = Trade(
            symbol="BTC/USD",
            entry_price=50000.0,
            exit_price=48000.0,
            quantity=1.0,
            pnl=-2000.0,
        )
        assert t.strategy == ""
        assert t.regime == "unknown"

    def test_frozen(self, sample_trade: Trade) -> None:
        with pytest.raises(ValidationError):
            sample_trade.pnl = 0.0  # type: ignore[misc]

    def test_negative_pnl_allowed(self) -> None:
        t = Trade(
            symbol="BTC/USD",
            entry_price=50000.0,
            exit_price=45000.0,
            quantity=1.0,
            pnl=-5000.0,
        )
        assert t.pnl == -5000.0

    def test_requires_symbol(self) -> None:
        with pytest.raises(ValidationError):
            Trade(
                entry_price=50000.0,
                exit_price=55000.0,
                quantity=1.0,
                pnl=5000.0,
            )  # type: ignore[call-arg]

    def test_serialization_roundtrip(self, sample_trade: Trade) -> None:
        data = sample_trade.model_dump()
        restored = Trade.model_validate(data)
        assert restored == sample_trade

    def test_json_roundtrip(self, sample_trade: Trade) -> None:
        json_str = sample_trade.model_dump_json()
        restored = Trade.model_validate_json(json_str)
        assert restored == sample_trade


# ===========================================================================
# StrategyStats
# ===========================================================================


class TestStrategyStats:
    """Tests for the StrategyStats model."""

    def test_creation(self) -> None:
        ss = StrategyStats(
            name="scalper",
            total_trades=50,
            win_rate=0.72,
            total_pnl=8000.0,
            avg_win=300.0,
            avg_loss=-100.0,
            profit_factor=3.0,
            max_consecutive_losses=3,
        )
        assert ss.name == "scalper"
        assert ss.total_trades == 50
        assert ss.win_rate == 0.72

    def test_defaults(self) -> None:
        ss = StrategyStats(name="empty")
        assert ss.total_trades == 0
        assert ss.win_rate == 0.0
        assert ss.total_pnl == 0.0
        assert ss.avg_win == 0.0
        assert ss.avg_loss == 0.0
        assert ss.profit_factor == 0.0
        assert ss.max_consecutive_losses == 0

    def test_frozen(self, sample_strategy_stats: StrategyStats) -> None:
        with pytest.raises(ValidationError):
            sample_strategy_stats.name = "other"  # type: ignore[misc]

    def test_total_trades_ge_zero(self) -> None:
        with pytest.raises(ValidationError):
            StrategyStats(name="bad", total_trades=-1)

    def test_win_rate_ge_zero(self) -> None:
        with pytest.raises(ValidationError):
            StrategyStats(name="bad", win_rate=-0.1)

    def test_win_rate_le_one(self) -> None:
        with pytest.raises(ValidationError):
            StrategyStats(name="bad", win_rate=1.1)

    def test_win_rate_boundaries(self) -> None:
        ss_zero = StrategyStats(name="zero", win_rate=0.0)
        assert ss_zero.win_rate == 0.0
        ss_one = StrategyStats(name="one", win_rate=1.0)
        assert ss_one.win_rate == 1.0

    def test_profit_factor_ge_zero(self) -> None:
        with pytest.raises(ValidationError):
            StrategyStats(name="bad", profit_factor=-1.0)

    def test_max_consecutive_losses_ge_zero(self) -> None:
        with pytest.raises(ValidationError):
            StrategyStats(name="bad", max_consecutive_losses=-1)

    def test_negative_total_pnl_allowed(self) -> None:
        ss = StrategyStats(name="loser", total_pnl=-5000.0)
        assert ss.total_pnl == -5000.0

    def test_serialization_roundtrip(self, sample_strategy_stats: StrategyStats) -> None:
        data = sample_strategy_stats.model_dump()
        restored = StrategyStats.model_validate(data)
        assert restored == sample_strategy_stats

    def test_json_roundtrip(self, sample_strategy_stats: StrategyStats) -> None:
        json_str = sample_strategy_stats.model_dump_json()
        restored = StrategyStats.model_validate_json(json_str)
        assert restored == sample_strategy_stats


# ===========================================================================
# AttributionReport
# ===========================================================================


class TestAttributionReport:
    """Tests for the AttributionReport model."""

    def test_creation(self, sample_strategy_stats: StrategyStats) -> None:
        report = AttributionReport(
            strategies={"momentum": sample_strategy_stats},
            total_pnl=15000.0,
            best_strategy="momentum",
            worst_strategy="momentum",
        )
        assert "momentum" in report.strategies
        assert report.total_pnl == 15000.0
        assert report.best_strategy == "momentum"
        assert report.worst_strategy == "momentum"

    def test_defaults(self) -> None:
        report = AttributionReport(strategies={})
        assert report.total_pnl == 0.0
        assert report.best_strategy == ""
        assert report.worst_strategy == ""

    def test_frozen(self, sample_attribution_report: AttributionReport) -> None:
        with pytest.raises(ValidationError):
            sample_attribution_report.total_pnl = 0.0  # type: ignore[misc]

    def test_multiple_strategies(self) -> None:
        s1 = StrategyStats(name="a", total_pnl=1000.0)
        s2 = StrategyStats(name="b", total_pnl=-500.0)
        report = AttributionReport(
            strategies={"a": s1, "b": s2},
            total_pnl=500.0,
            best_strategy="a",
            worst_strategy="b",
        )
        assert len(report.strategies) == 2
        assert report.strategies["a"].total_pnl == 1000.0
        assert report.strategies["b"].total_pnl == -500.0

    def test_requires_strategies(self) -> None:
        with pytest.raises(ValidationError):
            AttributionReport()  # type: ignore[call-arg]

    def test_serialization_roundtrip(
        self, sample_attribution_report: AttributionReport
    ) -> None:
        data = sample_attribution_report.model_dump()
        restored = AttributionReport.model_validate(data)
        assert restored == sample_attribution_report

    def test_json_roundtrip(self, sample_attribution_report: AttributionReport) -> None:
        json_str = sample_attribution_report.model_dump_json()
        restored = AttributionReport.model_validate_json(json_str)
        assert restored == sample_attribution_report


# ===========================================================================
# EquityPoint
# ===========================================================================


class TestEquityPoint:
    """Tests for the EquityPoint model."""

    def test_creation(self) -> None:
        ep = EquityPoint(timestamp=1704067200, value=100000.0)
        assert ep.timestamp == 1704067200
        assert ep.value == 100000.0

    def test_frozen(self, sample_equity_point: EquityPoint) -> None:
        with pytest.raises(ValidationError):
            sample_equity_point.value = 0.0  # type: ignore[misc]

    def test_requires_timestamp(self) -> None:
        with pytest.raises(ValidationError):
            EquityPoint(value=100000.0)  # type: ignore[call-arg]

    def test_requires_value(self) -> None:
        with pytest.raises(ValidationError):
            EquityPoint(timestamp=1704067200)  # type: ignore[call-arg]

    def test_negative_value_allowed(self) -> None:
        ep = EquityPoint(timestamp=1704067200, value=-500.0)
        assert ep.value == -500.0

    def test_serialization_roundtrip(self, sample_equity_point: EquityPoint) -> None:
        data = sample_equity_point.model_dump()
        restored = EquityPoint.model_validate(data)
        assert restored == sample_equity_point

    def test_json_roundtrip(self, sample_equity_point: EquityPoint) -> None:
        json_str = sample_equity_point.model_dump_json()
        restored = EquityPoint.model_validate_json(json_str)
        assert restored == sample_equity_point


# ===========================================================================
# MonteCarloResult
# ===========================================================================


class TestMonteCarloResult:
    """Tests for the MonteCarloResult model."""

    def test_creation(self) -> None:
        mc = MonteCarloResult(
            actual_final_value=120000.0,
            percentile=75.0,
            median_simulated=110000.0,
            p5_simulated=90000.0,
            p95_simulated=140000.0,
            worst_drawdown_p95=0.25,
            n_simulations=10000,
        )
        assert mc.actual_final_value == 120000.0
        assert mc.percentile == 75.0
        assert mc.median_simulated == 110000.0
        assert mc.p5_simulated == 90000.0
        assert mc.p95_simulated == 140000.0
        assert mc.worst_drawdown_p95 == 0.25
        assert mc.n_simulations == 10000

    def test_frozen(self, sample_monte_carlo_result: MonteCarloResult) -> None:
        with pytest.raises(ValidationError):
            sample_monte_carlo_result.percentile = 50.0  # type: ignore[misc]

    def test_percentile_ge_zero(self) -> None:
        with pytest.raises(ValidationError):
            MonteCarloResult(
                actual_final_value=100000.0,
                percentile=-1.0,
                median_simulated=100000.0,
                p5_simulated=90000.0,
                p95_simulated=110000.0,
                worst_drawdown_p95=0.1,
                n_simulations=1000,
            )

    def test_percentile_le_100(self) -> None:
        with pytest.raises(ValidationError):
            MonteCarloResult(
                actual_final_value=100000.0,
                percentile=101.0,
                median_simulated=100000.0,
                p5_simulated=90000.0,
                p95_simulated=110000.0,
                worst_drawdown_p95=0.1,
                n_simulations=1000,
            )

    def test_percentile_boundaries(self) -> None:
        mc_zero = MonteCarloResult(
            actual_final_value=100000.0,
            percentile=0.0,
            median_simulated=100000.0,
            p5_simulated=90000.0,
            p95_simulated=110000.0,
            worst_drawdown_p95=0.1,
            n_simulations=1000,
        )
        assert mc_zero.percentile == 0.0

        mc_hundred = MonteCarloResult(
            actual_final_value=100000.0,
            percentile=100.0,
            median_simulated=100000.0,
            p5_simulated=90000.0,
            p95_simulated=110000.0,
            worst_drawdown_p95=0.1,
            n_simulations=1000,
        )
        assert mc_hundred.percentile == 100.0

    def test_n_simulations_gt_zero(self) -> None:
        with pytest.raises(ValidationError):
            MonteCarloResult(
                actual_final_value=100000.0,
                percentile=50.0,
                median_simulated=100000.0,
                p5_simulated=90000.0,
                p95_simulated=110000.0,
                worst_drawdown_p95=0.1,
                n_simulations=0,
            )

    def test_n_simulations_negative(self) -> None:
        with pytest.raises(ValidationError):
            MonteCarloResult(
                actual_final_value=100000.0,
                percentile=50.0,
                median_simulated=100000.0,
                p5_simulated=90000.0,
                p95_simulated=110000.0,
                worst_drawdown_p95=0.1,
                n_simulations=-1,
            )

    def test_requires_all_fields(self) -> None:
        with pytest.raises(ValidationError):
            MonteCarloResult()  # type: ignore[call-arg]

    def test_serialization_roundtrip(
        self, sample_monte_carlo_result: MonteCarloResult
    ) -> None:
        data = sample_monte_carlo_result.model_dump()
        restored = MonteCarloResult.model_validate(data)
        assert restored == sample_monte_carlo_result

    def test_json_roundtrip(self, sample_monte_carlo_result: MonteCarloResult) -> None:
        json_str = sample_monte_carlo_result.model_dump_json()
        restored = MonteCarloResult.model_validate_json(json_str)
        assert restored == sample_monte_carlo_result
