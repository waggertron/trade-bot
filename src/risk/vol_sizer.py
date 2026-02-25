"""Volatility-targeted position sizer."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from src.risk.models import RiskContext, VolatilityRegime

if TYPE_CHECKING:
    from src.core.models import PortfolioSnapshot, Signal

_REGIME_MULTIPLIER: dict[VolatilityRegime, Decimal] = {
    VolatilityRegime.LOW: Decimal("1.0"),
    VolatilityRegime.MEDIUM: Decimal("0.75"),
    VolatilityRegime.HIGH: Decimal("0.5"),
}


class VolTargetedPositionSizer:
    """Sizes positions based on a target volatility contribution.

    The base size is a percentage of total portfolio value, scaled down
    in higher-volatility regimes.
    """

    def __init__(self, target_vol_contribution: float = 0.01) -> None:
        self._target_vol = target_vol_contribution

    @property
    def name(self) -> str:
        return "vol_targeted"

    async def compute_size(
        self,
        signal: Signal,
        portfolio: PortfolioSnapshot,
        risk_context: RiskContext,
    ) -> Decimal:
        """Returns trade value in base currency, capped at available cash."""
        base_size = portfolio.total_value * Decimal(str(self._target_vol))

        regime_multiplier = _REGIME_MULTIPLIER[risk_context.regime]
        size = base_size * regime_multiplier

        return min(size, portfolio.cash)
