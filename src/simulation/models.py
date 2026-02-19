"""Data models for the simulation system."""
from __future__ import annotations

from pydantic import ConfigDict, Field, model_validator

from src.core.base import StrictBase
from src.core.config import RiskLevel


class AllocationWeights(StrictBase):
    """Portfolio allocation weights per stock."""
    model_config = ConfigDict(frozen=True)

    mode: str = Field(default="equal_weight", pattern=r"^(equal_weight|custom)$")
    weights: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_custom_weights(self) -> AllocationWeights:
        if self.mode == "custom":
            if not self.weights:
                raise ValueError("weights must be non-empty when mode is 'custom'")
            for symbol, w in self.weights.items():
                if w < 0 or w > 1:
                    raise ValueError(
                        f"weight for {symbol} must be in [0, 1], got {w}"
                    )
            total = sum(self.weights.values())
            if abs(total - 1.0) >= 0.01:
                raise ValueError(
                    f"weights must sum to ~1.0 (tolerance 0.01), got {total}"
                )
        return self


class RebalanceConfig(StrictBase):
    """Rebalancing configuration."""
    model_config = ConfigDict(frozen=True)

    frequency: str = Field(default="none", pattern=r"^(none|daily|weekly|monthly)$")
    threshold_pct: float = Field(default=5.0, ge=0.0, le=100.0)


class SimulationConfig(StrictBase):
    """Configuration for a simulation run."""
    model_config = ConfigDict(frozen=True)

    stocks: list[str]
    initial_balance: float = Field(default=10_000.0, gt=0)
    train_days: int = Field(default=60, gt=0)
    test_days: int = Field(default=30, gt=0)
    risk_levels: list[RiskLevel] = Field(default_factory=lambda: list(RiskLevel))
    mc_simulations: int = Field(default=1000, gt=0)
    portfolio_mode: bool = False
    allocation: AllocationWeights = Field(default_factory=AllocationWeights)
    rebalance: RebalanceConfig = Field(default_factory=RebalanceConfig)


class StockSimResult(StrictBase):
    """Walk-forward backtest result for a single stock."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    initial_balance: float
    final_value: float
    total_pnl: float
    return_pct: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    equity_curve: list[float] = Field(default_factory=list)


class MonteCarloProjection(StrictBase):
    """Monte Carlo forward projection for a stock."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    median_final: float
    p5_final: float
    p95_final: float
    median_return_pct: float
    p5_return_pct: float
    p95_return_pct: float
    worst_drawdown_p95: float
    n_paths: int


class StrategyAssessment(StrictBase):
    """Per-strategy performance assessment across a simulation."""
    model_config = ConfigDict(frozen=True)

    strategy_name: str
    total_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_consecutive_losses: int = 0


class PortfolioMetrics(StrictBase):
    """Portfolio-level performance metrics."""
    model_config = ConfigDict(frozen=True)

    initial_balance: float = Field(gt=0)
    final_value: float
    total_return_pct: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    total_trades: int = Field(ge=0)
    equity_curve: list[float] = Field(default_factory=list)
    daily_returns: list[float] = Field(default_factory=list)
    rebalance_dates: list[int] = Field(default_factory=list)


class PortfolioMonteCarloProjection(StrictBase):
    """Correlated Monte Carlo projection for the entire portfolio."""
    model_config = ConfigDict(frozen=True)

    median_final: float
    p5_final: float
    p95_final: float
    median_return_pct: float
    p5_return_pct: float
    p95_return_pct: float
    worst_drawdown_p95: float
    n_paths: int = Field(gt=0)
    correlation_matrix: list[list[float]] = Field(default_factory=list)


class RiskLevelResult(StrictBase):
    """Aggregated results for one risk level across all stocks."""
    model_config = ConfigDict(frozen=True)

    risk_level: str
    stock_results: list[StockSimResult] = Field(default_factory=list)
    monte_carlo_projections: list[MonteCarloProjection] = Field(default_factory=list)
    strategy_assessments: list[StrategyAssessment] = Field(default_factory=list)
    total_return_pct: float = 0.0
    avg_sharpe: float = 0.0
    avg_max_drawdown: float = 0.0
    total_trades: int = 0
    portfolio_metrics: PortfolioMetrics | None = None
    portfolio_monte_carlo: PortfolioMonteCarloProjection | None = None


class Recommendation(StrictBase):
    """System recommendation based on simulation results."""
    model_config = ConfigDict(frozen=True)

    optimal_risk_level: str
    reasoning: str
    suggested_weights: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SimulationReport(StrictBase):
    """Complete simulation report across all risk levels."""

    id: str
    status: str = "pending"
    config: SimulationConfig
    risk_level_results: dict[str, RiskLevelResult] = Field(default_factory=dict)
    recommendation: Recommendation | None = None
    started_at: str = ""
    completed_at: str = ""
    error: str | None = None
