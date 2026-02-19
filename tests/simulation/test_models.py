"""Tests for simulation data models."""
from src.simulation.models import (
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
