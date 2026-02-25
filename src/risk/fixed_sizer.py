"""Fixed-percentage position sizer."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.models import PortfolioSnapshot, Signal
    from src.risk.models import RiskContext


class FixedPositionSizer:
    """Allocates a fixed percentage of total portfolio value per trade.

    The computed size is capped at the available cash in the portfolio.
    """

    def __init__(self, position_pct: float = 2.0) -> None:
        self._position_pct = position_pct

    @property
    def name(self) -> str:
        return "fixed"

    async def compute_size(
        self,
        signal: Signal,
        portfolio: PortfolioSnapshot,
        risk_context: RiskContext,
    ) -> Decimal:
        """Returns trade value in base currency, capped at available cash."""
        raw_size = portfolio.total_value * Decimal(str(self._position_pct)) / Decimal("100")
        return min(raw_size, portfolio.cash)
