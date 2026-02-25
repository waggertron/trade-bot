"""Risk-specific data models."""

from __future__ import annotations

from decimal import Decimal  # noqa: TC003
from enum import StrEnum

from pydantic import ConfigDict, Field

from src.core.base import StrictBase
from src.core.models import PortfolioSnapshot  # noqa: TC001


class VolatilityRegime(StrEnum):
    """Market volatility classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StrategyPerformance(StrictBase):
    """Performance statistics for a single strategy."""

    model_config = ConfigDict(frozen=True)

    name: str
    win_rate: float = Field(ge=0, le=1)
    avg_win: Decimal = Field(ge=0)
    avg_loss: Decimal = Field(ge=0)
    total_trades: int = Field(ge=0)
    recent_trades: int = Field(default=0, ge=0)
    recent_win_rate: float = Field(default=0.0, ge=0, le=1)


class RiskContext(StrictBase):
    """Snapshot of risk-relevant state used when evaluating a trade."""

    model_config = ConfigDict(frozen=True)

    regime: VolatilityRegime
    correlation_matrix: dict[str, float]
    strategy_stats: dict[str, StrategyPerformance]
    drawdown_from_peak: float = Field(ge=0, le=1)
    portfolio: PortfolioSnapshot
    daily_pnl: Decimal

    def get_correlation(self, sym_a: str, sym_b: str) -> float:
        """Look up correlation between two symbols.

        Checks both "A:B" and "B:A" orderings. Returns 0.0 if neither found.
        """
        key_forward = f"{sym_a}:{sym_b}"
        key_reverse = f"{sym_b}:{sym_a}"
        if key_forward in self.correlation_matrix:
            return self.correlation_matrix[key_forward]
        if key_reverse in self.correlation_matrix:
            return self.correlation_matrix[key_reverse]
        return 0.0
