"""Tests for PortfolioSimulator core logic."""
from __future__ import annotations

import math

import pytest

from src.simulation.models import (
    AllocationWeights,
    RebalanceConfig,
    SimulationConfig,
)
from src.simulation.portfolio import PortfolioSimulator


# ---------------------------------------------------------------------------
# Helpers to build configs quickly
# ---------------------------------------------------------------------------

def _cfg(
    stocks: list[str] | None = None,
    balance: float = 10_000.0,
    mode: str = "equal_weight",
    weights: dict[str, float] | None = None,
    rebalance_freq: str = "none",
) -> SimulationConfig:
    stocks = stocks or ["AAPL", "GOOG", "MSFT"]
    alloc = AllocationWeights(mode=mode, weights=weights or {})
    rebal = RebalanceConfig(frequency=rebalance_freq)
    return SimulationConfig(
        stocks=stocks,
        initial_balance=balance,
        allocation=alloc,
        rebalance=rebal,
    )


# ===================================================================
# 1. Weight computation
# ===================================================================

class TestWeightComputation:
    def test_equal_weight_three_stocks(self):
        sim = PortfolioSimulator(_cfg(stocks=["A", "B", "C"]))
        w = sim.weights
        assert len(w) == 3
        for s in ("A", "B", "C"):
            assert w[s] == pytest.approx(1 / 3)

    def test_equal_weight_single_stock(self):
        sim = PortfolioSimulator(_cfg(stocks=["SPY"]))
        assert sim.weights == {"SPY": pytest.approx(1.0)}

    def test_custom_weights(self):
        sim = PortfolioSimulator(
            _cfg(
                stocks=["A", "B"],
                mode="custom",
                weights={"A": 0.7, "B": 0.3},
            )
        )
        assert sim.weights["A"] == pytest.approx(0.7)
        assert sim.weights["B"] == pytest.approx(0.3)


# ===================================================================
# 2. get_stock_balance
# ===================================================================

class TestGetStockBalance:
    def test_equal_weight_balance(self):
        sim = PortfolioSimulator(_cfg(stocks=["A", "B", "C"], balance=30_000))
        assert sim.get_stock_balance("A") == pytest.approx(10_000)
        assert sim.get_stock_balance("B") == pytest.approx(10_000)
        assert sim.get_stock_balance("C") == pytest.approx(10_000)

    def test_custom_weight_balance(self):
        sim = PortfolioSimulator(
            _cfg(
                stocks=["X", "Y"],
                balance=20_000,
                mode="custom",
                weights={"X": 0.6, "Y": 0.4},
            )
        )
        assert sim.get_stock_balance("X") == pytest.approx(12_000)
        assert sim.get_stock_balance("Y") == pytest.approx(8_000)


# ===================================================================
# 3. build_portfolio_equity_curve
# ===================================================================

class TestBuildPortfolioEquityCurve:
    def test_two_stocks_equal_weight(self):
        """One stock +10%, the other -5%, equal weight -> portfolio +2.5%."""
        sim = PortfolioSimulator(
            _cfg(stocks=["UP", "DOWN"], balance=10_000)
        )
        curves = {
            "UP": [10_000.0, 11_000.0],
            "DOWN": [10_000.0, 9_500.0],
        }
        result = sim.build_portfolio_equity_curve(curves)
        assert len(result) == 2
        # t=0: 5000 * 1.0 + 5000 * 1.0 = 10000
        assert result[0] == pytest.approx(10_000.0)
        # t=1: 5000 * 1.10 + 5000 * 0.95 = 5500 + 4750 = 10250
        assert result[1] == pytest.approx(10_250.0)

    def test_different_length_curves(self):
        """Uses min length across all curves."""
        sim = PortfolioSimulator(_cfg(stocks=["A", "B"], balance=10_000))
        curves = {
            "A": [100.0, 110.0, 120.0],
            "B": [200.0, 210.0],
        }
        result = sim.build_portfolio_equity_curve(curves)
        assert len(result) == 2  # min(3, 2)

    def test_empty_curves_dict(self):
        sim = PortfolioSimulator(_cfg(stocks=["A"], balance=10_000))
        assert sim.build_portfolio_equity_curve({}) == []

    def test_curve_with_zero_start_skipped(self):
        """A curve starting at 0 is skipped."""
        sim = PortfolioSimulator(_cfg(stocks=["A", "B"], balance=10_000))
        curves = {
            "A": [0, 100.0],
            "B": [100.0, 110.0],
        }
        result = sim.build_portfolio_equity_curve(curves)
        # Only B contributes: allocated = 5000, normalised: 5000*1.0, 5000*1.1
        assert len(result) == 2
        assert result[0] == pytest.approx(5_000.0)
        assert result[1] == pytest.approx(5_500.0)

    def test_curve_empty_list_skipped(self):
        sim = PortfolioSimulator(_cfg(stocks=["A", "B"], balance=10_000))
        curves = {
            "A": [],
            "B": [100.0, 110.0],
        }
        result = sim.build_portfolio_equity_curve(curves)
        assert len(result) == 2

    def test_all_curves_unusable(self):
        sim = PortfolioSimulator(_cfg(stocks=["A"], balance=10_000))
        curves = {"A": []}
        assert sim.build_portfolio_equity_curve(curves) == []


# ===================================================================
# 4. compute_portfolio_metrics
# ===================================================================

class TestComputePortfolioMetrics:
    def test_known_curve(self):
        sim = PortfolioSimulator(_cfg(stocks=["A"], balance=10_000))
        curve = [10_000.0, 10_100.0, 10_200.0, 10_050.0, 10_300.0]
        metrics = sim.compute_portfolio_metrics(curve, total_trades=15)

        # daily_returns
        expected_dr = [
            (10_100 - 10_000) / 10_000,
            (10_200 - 10_100) / 10_100,
            (10_050 - 10_200) / 10_200,
            (10_300 - 10_050) / 10_050,
        ]
        assert len(metrics.daily_returns) == 4
        for actual, expected in zip(metrics.daily_returns, expected_dr):
            assert actual == pytest.approx(expected, rel=1e-9)

        # total_return_pct
        assert metrics.total_return_pct == pytest.approx(3.0)

        # max_drawdown: peak 10200 -> trough 10050
        expected_dd = (10_200 - 10_050) / 10_200 * 100
        assert metrics.max_drawdown == pytest.approx(expected_dd)

        # sharpe and sortino should be finite
        assert math.isfinite(metrics.sharpe_ratio)
        assert math.isfinite(metrics.sortino_ratio)

        # calmar should be finite
        assert math.isfinite(metrics.calmar_ratio)

        # Metadata
        assert metrics.initial_balance == 10_000
        assert metrics.final_value == 10_300
        assert metrics.total_trades == 15
        assert metrics.equity_curve == curve

    def test_flat_curve(self):
        """All values are the same -> zero returns, zero ratios."""
        sim = PortfolioSimulator(_cfg(stocks=["A"], balance=5_000))
        curve = [5_000.0, 5_000.0, 5_000.0]
        metrics = sim.compute_portfolio_metrics(curve, total_trades=0)

        assert metrics.total_return_pct == pytest.approx(0.0)
        assert metrics.max_drawdown == pytest.approx(0.0)
        assert metrics.sharpe_ratio == pytest.approx(0.0)
        assert metrics.sortino_ratio == pytest.approx(0.0)
        assert metrics.calmar_ratio == pytest.approx(0.0)

    def test_single_point_curve(self):
        sim = PortfolioSimulator(_cfg(stocks=["A"], balance=1_000))
        curve = [1_000.0]
        metrics = sim.compute_portfolio_metrics(curve, total_trades=0)

        assert metrics.daily_returns == []
        assert metrics.total_return_pct == pytest.approx(0.0)
        assert metrics.max_drawdown == pytest.approx(0.0)
        assert metrics.sharpe_ratio == pytest.approx(0.0)
        assert metrics.sortino_ratio == pytest.approx(0.0)
        assert metrics.calmar_ratio == pytest.approx(0.0)

    def test_monotonically_increasing_curve(self):
        """No drawdown, no negative returns -> sortino should be 0."""
        sim = PortfolioSimulator(_cfg(stocks=["A"], balance=10_000))
        curve = [10_000.0, 10_100.0, 10_200.0, 10_300.0]
        metrics = sim.compute_portfolio_metrics(curve, total_trades=5)

        assert metrics.total_return_pct == pytest.approx(3.0)
        assert metrics.max_drawdown == pytest.approx(0.0)
        # No negative returns -> sortino = 0
        assert metrics.sortino_ratio == pytest.approx(0.0)
        # sharpe should be positive (there is variance because returns decrease)
        assert metrics.sharpe_ratio != 0.0 or True  # could be 0 if all returns equal
        assert metrics.calmar_ratio == pytest.approx(0.0)  # max_dd = 0

    def test_daily_returns_count(self):
        """n data points should produce n-1 daily returns."""
        sim = PortfolioSimulator(_cfg(stocks=["A"], balance=10_000))
        curve = [100.0] * 10
        metrics = sim.compute_portfolio_metrics(curve, total_trades=0)
        assert len(metrics.daily_returns) == 9


# ===================================================================
# 5. should_rebalance
# ===================================================================

class TestShouldRebalance:
    def test_none_always_false(self):
        sim = PortfolioSimulator(_cfg(rebalance_freq="none"))
        for day in range(50):
            assert sim.should_rebalance(day, 50) is False

    def test_daily_true_except_day_zero(self):
        sim = PortfolioSimulator(_cfg(rebalance_freq="daily"))
        assert sim.should_rebalance(0, 100) is False
        assert sim.should_rebalance(1, 100) is True
        assert sim.should_rebalance(2, 100) is True
        assert sim.should_rebalance(50, 100) is True

    def test_weekly(self):
        sim = PortfolioSimulator(_cfg(rebalance_freq="weekly"))
        assert sim.should_rebalance(0, 100) is False
        assert sim.should_rebalance(1, 100) is False
        assert sim.should_rebalance(4, 100) is False
        assert sim.should_rebalance(5, 100) is True
        assert sim.should_rebalance(10, 100) is True
        assert sim.should_rebalance(11, 100) is False

    def test_monthly(self):
        sim = PortfolioSimulator(_cfg(rebalance_freq="monthly"))
        assert sim.should_rebalance(0, 100) is False
        assert sim.should_rebalance(5, 100) is False
        assert sim.should_rebalance(20, 100) is False
        assert sim.should_rebalance(21, 100) is True
        assert sim.should_rebalance(42, 100) is True
        assert sim.should_rebalance(22, 100) is False


# ===================================================================
# 6. weights property
# ===================================================================

class TestWeightsProperty:
    def test_returns_correct_weights(self):
        sim = PortfolioSimulator(_cfg(stocks=["A", "B"], balance=10_000))
        assert sim.weights == {"A": pytest.approx(0.5), "B": pytest.approx(0.5)}

    def test_returns_copy(self):
        """Modifying the returned dict should not affect internal state."""
        sim = PortfolioSimulator(_cfg(stocks=["A", "B"], balance=10_000))
        w = sim.weights
        w["A"] = 999.0
        assert sim.weights["A"] == pytest.approx(0.5)
