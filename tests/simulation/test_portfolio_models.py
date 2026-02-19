"""Tests for portfolio simulation data models."""
import pytest
from pydantic import ValidationError

from src.simulation.models import (
    AllocationWeights,
    RebalanceConfig,
    PortfolioMetrics,
    PortfolioMonteCarloProjection,
    SimulationConfig,
    RiskLevelResult,
)


# ---------------------------------------------------------------------------
# Backward compatibility — old-style SimulationConfig without new fields
# ---------------------------------------------------------------------------


class TestSimulationConfigBackwardCompat:
    """Existing SimulationConfig usage must continue to work unchanged."""

    def test_old_style_config_still_works(self):
        cfg = SimulationConfig(stocks=["AAPL", "MSFT"])
        assert cfg.stocks == ["AAPL", "MSFT"]
        assert cfg.initial_balance == 10_000.0
        assert cfg.portfolio_mode is False
        assert cfg.allocation.mode == "equal_weight"
        assert cfg.allocation.weights == {}
        assert cfg.rebalance.frequency == "none"
        assert cfg.rebalance.threshold_pct == 5.0
        assert cfg.mc_seed is None

    def test_old_style_config_with_explicit_fields(self):
        cfg = SimulationConfig(
            stocks=["TSLA"],
            initial_balance=50_000.0,
            train_days=90,
            test_days=45,
            mc_simulations=500,
        )
        assert cfg.initial_balance == 50_000.0
        assert cfg.train_days == 90
        assert cfg.test_days == 45
        assert cfg.mc_simulations == 500
        # New fields take defaults
        assert cfg.portfolio_mode is False


# ---------------------------------------------------------------------------
# AllocationWeights
# ---------------------------------------------------------------------------


class TestAllocationWeights:
    def test_defaults(self):
        aw = AllocationWeights()
        assert aw.mode == "equal_weight"
        assert aw.weights == {}

    def test_equal_weight_mode(self):
        aw = AllocationWeights(mode="equal_weight")
        assert aw.mode == "equal_weight"

    def test_custom_mode_with_weights(self):
        aw = AllocationWeights(
            mode="custom",
            weights={"AAPL": 0.5, "MSFT": 0.3, "GOOG": 0.2},
        )
        assert aw.mode == "custom"
        assert aw.weights["AAPL"] == 0.5
        assert sum(aw.weights.values()) == pytest.approx(1.0)

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValidationError, match="pattern"):
            AllocationWeights(mode="invalid")

    def test_invalid_mode_value_price_weighted(self):
        with pytest.raises(ValidationError, match="pattern"):
            AllocationWeights(mode="price_weighted")

    def test_frozen(self):
        aw = AllocationWeights()
        with pytest.raises(ValidationError):
            aw.mode = "custom"

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError, match="extra"):
            AllocationWeights(mode="equal_weight", extra_field="bad")

    def test_custom_weights_not_summing_to_one_rejected(self):
        with pytest.raises(ValidationError, match="sum to ~1.0"):
            AllocationWeights(
                mode="custom",
                weights={"AAPL": 0.5, "MSFT": 0.2},
            )

    def test_custom_weights_negative_value_rejected(self):
        with pytest.raises(ValidationError, match=r"must be in \[0, 1\]"):
            AllocationWeights(
                mode="custom",
                weights={"AAPL": -0.5, "MSFT": 1.5},
            )

    def test_custom_weights_empty_dict_rejected(self):
        with pytest.raises(ValidationError, match="non-empty"):
            AllocationWeights(mode="custom", weights={})

    def test_custom_weights_value_above_one_rejected(self):
        with pytest.raises(ValidationError, match=r"must be in \[0, 1\]"):
            AllocationWeights(
                mode="custom",
                weights={"AAPL": 1.5},
            )


# ---------------------------------------------------------------------------
# RebalanceConfig
# ---------------------------------------------------------------------------


class TestRebalanceConfig:
    def test_defaults(self):
        rc = RebalanceConfig()
        assert rc.frequency == "none"
        assert rc.threshold_pct == 5.0

    def test_all_valid_frequencies(self):
        for freq in ("none", "daily", "weekly", "monthly"):
            rc = RebalanceConfig(frequency=freq)
            assert rc.frequency == freq

    def test_invalid_frequency_rejected(self):
        with pytest.raises(ValidationError, match="pattern"):
            RebalanceConfig(frequency="yearly")

    def test_invalid_frequency_quarterly(self):
        with pytest.raises(ValidationError, match="pattern"):
            RebalanceConfig(frequency="quarterly")

    def test_threshold_lower_bound(self):
        rc = RebalanceConfig(threshold_pct=0.0)
        assert rc.threshold_pct == 0.0

    def test_threshold_upper_bound(self):
        rc = RebalanceConfig(threshold_pct=100.0)
        assert rc.threshold_pct == 100.0

    def test_threshold_below_zero_rejected(self):
        with pytest.raises(ValidationError, match="greater than or equal to"):
            RebalanceConfig(threshold_pct=-0.1)

    def test_threshold_above_100_rejected(self):
        with pytest.raises(ValidationError, match="less than or equal to"):
            RebalanceConfig(threshold_pct=100.1)

    def test_frozen(self):
        rc = RebalanceConfig()
        with pytest.raises(ValidationError):
            rc.frequency = "daily"


# ---------------------------------------------------------------------------
# PortfolioMetrics
# ---------------------------------------------------------------------------


class TestPortfolioMetrics:
    @pytest.fixture()
    def sample_metrics(self):
        return PortfolioMetrics(
            initial_balance=10_000.0,
            final_value=12_500.0,
            total_return_pct=25.0,
            max_drawdown=8.5,
            sharpe_ratio=1.8,
            sortino_ratio=2.1,
            calmar_ratio=2.94,
            total_trades=150,
            equity_curve=[10000.0, 11000.0, 12500.0],
            daily_returns=[0.0, 0.1, 0.136],
            rebalance_dates=[5, 10, 15],
        )

    def test_construction(self, sample_metrics):
        assert sample_metrics.initial_balance == 10_000.0
        assert sample_metrics.final_value == 12_500.0
        assert sample_metrics.total_return_pct == 25.0
        assert sample_metrics.max_drawdown == 8.5
        assert sample_metrics.sharpe_ratio == 1.8
        assert sample_metrics.sortino_ratio == 2.1
        assert sample_metrics.calmar_ratio == 2.94
        assert sample_metrics.total_trades == 150

    def test_list_fields_default_empty(self):
        pm = PortfolioMetrics(
            initial_balance=10_000.0,
            final_value=10_000.0,
            total_return_pct=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            total_trades=0,
        )
        assert pm.equity_curve == []
        assert pm.daily_returns == []
        assert pm.rebalance_dates == []

    def test_frozen(self, sample_metrics):
        with pytest.raises(ValidationError):
            sample_metrics.final_value = 99999.0

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError, match="extra"):
            PortfolioMetrics(
                initial_balance=10_000.0,
                final_value=10_000.0,
                total_return_pct=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                total_trades=0,
                bogus_field="nope",
            )

    def test_initial_balance_zero_rejected(self):
        with pytest.raises(ValidationError, match="greater than"):
            PortfolioMetrics(
                initial_balance=0,
                final_value=10_000.0,
                total_return_pct=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                total_trades=0,
            )

    def test_initial_balance_negative_rejected(self):
        with pytest.raises(ValidationError, match="greater than"):
            PortfolioMetrics(
                initial_balance=-1000.0,
                final_value=10_000.0,
                total_return_pct=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                total_trades=0,
            )

    def test_total_trades_negative_rejected(self):
        with pytest.raises(ValidationError, match="greater than or equal"):
            PortfolioMetrics(
                initial_balance=10_000.0,
                final_value=10_000.0,
                total_return_pct=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                total_trades=-1,
            )


# ---------------------------------------------------------------------------
# PortfolioMonteCarloProjection
# ---------------------------------------------------------------------------


class TestPortfolioMonteCarloProjection:
    @pytest.fixture()
    def sample_projection(self):
        return PortfolioMonteCarloProjection(
            median_final=12_000.0,
            p5_final=9_000.0,
            p95_final=15_000.0,
            median_return_pct=20.0,
            p5_return_pct=-10.0,
            p95_return_pct=50.0,
            worst_drawdown_p95=25.0,
            n_paths=1000,
            correlation_matrix=[[1.0, 0.5], [0.5, 1.0]],
        )

    def test_construction(self, sample_projection):
        assert sample_projection.median_final == 12_000.0
        assert sample_projection.p5_final == 9_000.0
        assert sample_projection.p95_final == 15_000.0
        assert sample_projection.n_paths == 1000
        assert sample_projection.correlation_matrix == [[1.0, 0.5], [0.5, 1.0]]

    def test_correlation_matrix_default_empty(self):
        proj = PortfolioMonteCarloProjection(
            median_final=10_000.0,
            p5_final=8_000.0,
            p95_final=12_000.0,
            median_return_pct=0.0,
            p5_return_pct=-20.0,
            p95_return_pct=20.0,
            worst_drawdown_p95=30.0,
            n_paths=500,
        )
        assert proj.correlation_matrix == []

    def test_frozen(self, sample_projection):
        with pytest.raises(ValidationError):
            sample_projection.n_paths = 5000

    def test_n_paths_zero_rejected(self):
        with pytest.raises(ValidationError, match="greater than"):
            PortfolioMonteCarloProjection(
                median_final=10_000.0,
                p5_final=8_000.0,
                p95_final=12_000.0,
                median_return_pct=0.0,
                p5_return_pct=-20.0,
                p95_return_pct=20.0,
                worst_drawdown_p95=30.0,
                n_paths=0,
            )

    def test_n_paths_negative_rejected(self):
        with pytest.raises(ValidationError, match="greater than"):
            PortfolioMonteCarloProjection(
                median_final=10_000.0,
                p5_final=8_000.0,
                p95_final=12_000.0,
                median_return_pct=0.0,
                p5_return_pct=-20.0,
                p95_return_pct=20.0,
                worst_drawdown_p95=30.0,
                n_paths=-5,
            )


# ---------------------------------------------------------------------------
# SimulationConfig with new portfolio fields
# ---------------------------------------------------------------------------


class TestSimulationConfigPortfolioFields:
    def test_portfolio_mode_enabled(self):
        cfg = SimulationConfig(
            stocks=["AAPL", "MSFT", "GOOG"],
            portfolio_mode=True,
            allocation=AllocationWeights(
                mode="custom",
                weights={"AAPL": 0.4, "MSFT": 0.35, "GOOG": 0.25},
            ),
            rebalance=RebalanceConfig(frequency="weekly", threshold_pct=3.0),
        )
        assert cfg.portfolio_mode is True
        assert cfg.allocation.mode == "custom"
        assert cfg.allocation.weights["AAPL"] == 0.4
        assert cfg.rebalance.frequency == "weekly"
        assert cfg.rebalance.threshold_pct == 3.0

    def test_portfolio_mode_with_equal_weight(self):
        cfg = SimulationConfig(
            stocks=["AAPL", "MSFT"],
            portfolio_mode=True,
        )
        assert cfg.portfolio_mode is True
        assert cfg.allocation.mode == "equal_weight"
        assert cfg.rebalance.frequency == "none"

    def test_config_frozen(self):
        cfg = SimulationConfig(stocks=["AAPL"])
        with pytest.raises(ValidationError):
            cfg.portfolio_mode = True

    def test_allocation_from_dict(self):
        """Verify nested dict auto-coercion works for AllocationWeights."""
        cfg = SimulationConfig(
            stocks=["AAPL"],
            allocation={"mode": "custom", "weights": {"AAPL": 1.0}},
        )
        assert cfg.allocation.mode == "custom"
        assert cfg.allocation.weights == {"AAPL": 1.0}

    def test_rebalance_from_dict(self):
        """Verify nested dict auto-coercion works for RebalanceConfig."""
        cfg = SimulationConfig(
            stocks=["AAPL"],
            rebalance={"frequency": "monthly", "threshold_pct": 10.0},
        )
        assert cfg.rebalance.frequency == "monthly"
        assert cfg.rebalance.threshold_pct == 10.0

    def test_mc_seed_default_none(self):
        """mc_seed defaults to None (non-deterministic)."""
        cfg = SimulationConfig(stocks=["AAPL"])
        assert cfg.mc_seed is None

    def test_mc_seed_explicit_value(self):
        """mc_seed accepts an explicit integer seed."""
        cfg = SimulationConfig(stocks=["AAPL"], mc_seed=42)
        assert cfg.mc_seed == 42

    def test_mc_seed_explicit_none(self):
        """mc_seed accepts explicit None."""
        cfg = SimulationConfig(stocks=["AAPL"], mc_seed=None)
        assert cfg.mc_seed is None

    def test_mc_seed_frozen(self):
        """mc_seed cannot be mutated on a frozen config."""
        cfg = SimulationConfig(stocks=["AAPL"], mc_seed=42)
        with pytest.raises(ValidationError):
            cfg.mc_seed = 99


# ---------------------------------------------------------------------------
# RiskLevelResult with and without portfolio fields
# ---------------------------------------------------------------------------


class TestRiskLevelResultPortfolioFields:
    def test_without_portfolio_fields(self):
        """Old-style construction without portfolio_metrics / portfolio_monte_carlo."""
        result = RiskLevelResult(risk_level="moderate")
        assert result.risk_level == "moderate"
        assert result.portfolio_metrics is None
        assert result.portfolio_monte_carlo is None

    def test_with_portfolio_metrics(self):
        pm = PortfolioMetrics(
            initial_balance=10_000.0,
            final_value=11_000.0,
            total_return_pct=10.0,
            max_drawdown=5.0,
            sharpe_ratio=1.5,
            sortino_ratio=1.8,
            calmar_ratio=2.0,
            total_trades=50,
        )
        result = RiskLevelResult(
            risk_level="aggressive",
            portfolio_metrics=pm,
        )
        assert result.portfolio_metrics is not None
        assert result.portfolio_metrics.total_return_pct == 10.0

    def test_with_portfolio_monte_carlo(self):
        pmc = PortfolioMonteCarloProjection(
            median_final=11_000.0,
            p5_final=9_000.0,
            p95_final=13_000.0,
            median_return_pct=10.0,
            p5_return_pct=-10.0,
            p95_return_pct=30.0,
            worst_drawdown_p95=20.0,
            n_paths=1000,
        )
        result = RiskLevelResult(
            risk_level="conservative",
            portfolio_monte_carlo=pmc,
        )
        assert result.portfolio_monte_carlo is not None
        assert result.portfolio_monte_carlo.n_paths == 1000

    def test_with_both_portfolio_fields(self):
        pm = PortfolioMetrics(
            initial_balance=10_000.0,
            final_value=12_000.0,
            total_return_pct=20.0,
            max_drawdown=7.0,
            sharpe_ratio=1.9,
            sortino_ratio=2.2,
            calmar_ratio=2.86,
            total_trades=100,
            equity_curve=[10000.0, 11000.0, 12000.0],
            daily_returns=[0.0, 0.1, 0.09],
            rebalance_dates=[5, 10],
        )
        pmc = PortfolioMonteCarloProjection(
            median_final=12_500.0,
            p5_final=9_500.0,
            p95_final=15_500.0,
            median_return_pct=25.0,
            p5_return_pct=-5.0,
            p95_return_pct=55.0,
            worst_drawdown_p95=22.0,
            n_paths=2000,
            correlation_matrix=[[1.0, 0.6], [0.6, 1.0]],
        )
        result = RiskLevelResult(
            risk_level="moderate",
            total_return_pct=20.0,
            avg_sharpe=1.9,
            portfolio_metrics=pm,
            portfolio_monte_carlo=pmc,
        )
        assert result.portfolio_metrics.final_value == 12_000.0
        assert result.portfolio_monte_carlo.correlation_matrix[0][1] == 0.6

    def test_frozen(self):
        result = RiskLevelResult(risk_level="moderate")
        with pytest.raises(ValidationError):
            result.portfolio_metrics = PortfolioMetrics(
                initial_balance=10_000.0,
                final_value=10_000.0,
                total_return_pct=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                total_trades=0,
            )
