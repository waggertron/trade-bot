"""Analytics data models for strategy attribution and performance analysis."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.core.models import Fill


class AttributedFill(BaseModel):
    """A fill attributed to a specific strategy and volatility regime."""

    model_config = ConfigDict(frozen=True)

    fill: Fill
    strategy: str
    regime: str = "unknown"


class Trade(BaseModel):
    """A paired buy/sell trade with computed PnL."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    strategy: str = ""
    regime: str = "unknown"


class StrategyStats(BaseModel):
    """Aggregate statistics for a single strategy."""

    model_config = ConfigDict(frozen=True)

    name: str
    total_trades: int = Field(default=0, ge=0)
    win_rate: float = Field(default=0.0, ge=0, le=1)
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = Field(default=0.0, ge=0)
    max_consecutive_losses: int = Field(default=0, ge=0)


class AttributionReport(BaseModel):
    """Full attribution report across all strategies."""

    model_config = ConfigDict(frozen=True)

    strategies: dict[str, StrategyStats]
    total_pnl: float = 0.0
    best_strategy: str = ""
    worst_strategy: str = ""


class EquityPoint(BaseModel):
    """A single point on the equity curve."""

    model_config = ConfigDict(frozen=True)

    timestamp: int
    value: float


class MonteCarloResult(BaseModel):
    """Results from a Monte Carlo simulation of trade returns."""

    model_config = ConfigDict(frozen=True)

    actual_final_value: float
    percentile: float = Field(ge=0, le=100)
    median_simulated: float
    p5_simulated: float
    p95_simulated: float
    worst_drawdown_p95: float
    n_simulations: int = Field(gt=0)
