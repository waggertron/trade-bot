"""Risk protocols — PositionSizer and future risk-related interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from decimal import Decimal

    from src.core.models import PortfolioSnapshot, Signal
    from src.risk.models import RiskContext


@runtime_checkable
class PositionSizer(Protocol):
    """Protocol for computing trade size given a signal and portfolio state."""

    @property
    def name(self) -> str: ...

    async def compute_size(
        self,
        signal: Signal,
        portfolio: PortfolioSnapshot,
        risk_context: RiskContext,
    ) -> Decimal:
        """Returns trade value in base currency (not quantity)."""
        ...
