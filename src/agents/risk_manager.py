from __future__ import annotations

from decimal import Decimal

from src.core.config import RiskSettings
from src.core.models import (
    PortfolioSnapshot, RiskAction, RiskDecision, Signal, SignalDirection,
)


class RiskManager:
    def __init__(self, settings: RiskSettings):
        self._settings = settings
        self._daily_pnl = Decimal("0")

    def record_daily_pnl(self, pnl: Decimal) -> None:
        self._daily_pnl = pnl

    def reset_daily_pnl(self) -> None:
        self._daily_pnl = Decimal("0")

    async def evaluate_trade(
        self, signal: Signal, portfolio: PortfolioSnapshot,
    ) -> RiskDecision:
        # Check daily loss limit
        if portfolio.total_value > 0:
            daily_loss_pct = abs(self._daily_pnl) / portfolio.total_value * 100
            if self._daily_pnl < 0 and daily_loss_pct >= self._settings.daily_loss_limit_pct:
                return RiskDecision(
                    action=RiskAction.VETO,
                    reason=f"Daily loss limit exceeded: {daily_loss_pct:.1f}% "
                           f"(limit: {self._settings.daily_loss_limit_pct}%)",
                )

        # Check max open positions
        if len(portfolio.positions) >= self._settings.max_open_positions:
            existing_symbols = {p.symbol for p in portfolio.positions}
            if signal.symbol not in existing_symbols:
                return RiskDecision(
                    action=RiskAction.VETO,
                    reason=f"Max open positions reached: {len(portfolio.positions)} "
                           f"(limit: {self._settings.max_open_positions})",
                )

        return RiskDecision(action=RiskAction.APPROVE, reason="All risk checks passed")

    async def check_portfolio_health(
        self, portfolio: PortfolioSnapshot,
    ) -> list[str]:
        warnings = []
        if portfolio.total_value > 0:
            daily_loss_pct = abs(self._daily_pnl) / portfolio.total_value * 100
            if self._daily_pnl < 0 and daily_loss_pct >= self._settings.daily_loss_limit_pct * 0.8:
                warnings.append(
                    f"Approaching daily loss limit: {daily_loss_pct:.1f}% "
                    f"(limit: {self._settings.daily_loss_limit_pct}%)"
                )
        return warnings
