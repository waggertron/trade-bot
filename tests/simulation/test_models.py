"""Tests for simulation data models."""
import pytest

from src.simulation.models import (
    BenchmarkResult,
    SimulationConfig,
    StockSimResult,
    RiskLevelResult,
    MonteCarloProjection,
    StrategyAssessment,
    SimulationReport,
    Recommendation,
)
from src.core.config import RiskLevel


def test_simulation_config_defaults():
    cfg = SimulationConfig(stocks=["AAPL"])
    assert cfg.initial_balance == 10_000.0
    assert cfg.train_days == 60
    assert cfg.test_days == 30
    assert cfg.risk_levels == list(RiskLevel)
    assert cfg.mc_simulations == 1000
    assert cfg.max_position_pct is None


def test_simulation_config_max_position_pct_override():
    cfg = SimulationConfig(stocks=["AAPL"], max_position_pct=2.5)
    assert cfg.max_position_pct == 2.5


def test_simulation_config_max_position_pct_validation():
    import pytest
    with pytest.raises(Exception):
        SimulationConfig(stocks=["AAPL"], max_position_pct=0.05)  # below 0.1
    with pytest.raises(Exception):
        SimulationConfig(stocks=["AAPL"], max_position_pct=101.0)  # above 100


def test_stock_sim_result_return_pct():
    r = StockSimResult(
        symbol="AAPL",
        initial_balance=10000.0,
        final_value=11000.0,
        total_pnl=1000.0,
        return_pct=10.0,
        max_drawdown=5.0,
        sharpe_ratio=1.5,
        total_trades=20,
        winning_trades=12,
        losing_trades=8,
        win_rate=0.6,
        equity_curve=[10000.0, 10500.0, 11000.0],
    )
    assert r.return_pct == 10.0
    assert r.win_rate == 0.6


def test_recommendation_model():
    rec = Recommendation(
        optimal_risk_level="moderate",
        reasoning="Best risk-adjusted returns",
        suggested_weights={"momentum": 0.6, "quantitative": 0.4},
        confidence=0.75,
    )
    assert rec.optimal_risk_level == "moderate"
    assert rec.confidence == 0.75


def test_benchmark_result_construction():
    br = BenchmarkResult(
        name="SPY Buy-and-Hold",
        initial_balance=10000.0,
        final_value=11200.0,
        return_pct=12.0,
        max_drawdown=5.5,
        sharpe_ratio=1.2,
        equity_curve=[10000.0, 10500.0, 11200.0],
    )
    assert br.name == "SPY Buy-and-Hold"
    assert br.return_pct == 12.0
    assert br.equity_curve == [10000.0, 10500.0, 11200.0]


def test_benchmark_result_frozen():
    br = BenchmarkResult(
        name="SPY DCA",
        initial_balance=10000.0,
        final_value=10500.0,
        return_pct=5.0,
        max_drawdown=3.0,
        sharpe_ratio=0.9,
    )
    with pytest.raises(Exception):
        br.name = "changed"


def test_simulation_report_benchmarks():
    br = BenchmarkResult(
        name="SPY Buy-and-Hold",
        initial_balance=10000.0,
        final_value=11200.0,
        return_pct=12.0,
        max_drawdown=5.5,
        sharpe_ratio=1.2,
    )
    report = SimulationReport(
        id="test123",
        config=SimulationConfig(stocks=["AAPL"]),
        benchmarks={"spy_buy_hold": br},
    )
    assert "spy_buy_hold" in report.benchmarks
    assert report.benchmarks["spy_buy_hold"].return_pct == 12.0


def test_simulation_report_benchmarks_default_empty():
    report = SimulationReport(
        id="test456",
        config=SimulationConfig(stocks=["AAPL"]),
    )
    assert report.benchmarks == {}
