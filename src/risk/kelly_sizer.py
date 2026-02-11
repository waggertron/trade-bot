"""Kelly Criterion position sizer."""

from __future__ import annotations

from decimal import Decimal

from src.core.models import PortfolioSnapshot, Signal
from src.risk.models import RiskContext


class KellyPositionSizer:
    """Sizes positions using the Kelly Criterion with a configurable multiplier.

    Falls back to 1% of portfolio value when strategy statistics are
    insufficient (fewer than 20 trades, missing stats, or zero avg_loss).
    The Kelly fraction is capped at 5% to prevent over-sizing.
    """

    def __init__(self, kelly_multiplier: float = 0.5) -> None:
        self._multiplier = kelly_multiplier

    @property
    def name(self) -> str:
        return "kelly"

    async def compute_size(
        self,
        signal: Signal,
        portfolio: PortfolioSnapshot,
        risk_context: RiskContext,
    ) -> Decimal:
        """Returns trade value in base currency, capped at available cash."""
        stats = risk_context.strategy_stats.get(signal.strategy_name)

        # Fallback: no stats or insufficient trades
        if stats is None or stats.total_trades < 20:
            return self._fallback(portfolio)

        # Fallback: avg_loss is zero (can't compute payoff ratio)
        if stats.avg_loss == 0:
            return self._fallback(portfolio)

        # Kelly Criterion calculation
        payoff_ratio = stats.avg_win / abs(stats.avg_loss)
        win_prob = Decimal(str(stats.win_rate))
        loss_prob = Decimal("1") - win_prob

        kelly = (win_prob * payoff_ratio - loss_prob) / payoff_ratio

        # Apply multiplier and floor at zero
        kelly = max(Decimal("0"), kelly * Decimal(str(self._multiplier)))

        # Cap at 5%
        kelly = min(kelly, Decimal("0.05"))

        size = portfolio.total_value * kelly
        return min(size, portfolio.cash)

    @staticmethod
    def _fallback(portfolio: PortfolioSnapshot) -> Decimal:
        """1% of total portfolio value, capped at cash."""
        size = portfolio.total_value * Decimal("0.01")
        return min(size, portfolio.cash)
