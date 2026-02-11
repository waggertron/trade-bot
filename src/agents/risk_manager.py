from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from src.core.config import RiskSettings
from src.core.models import (
    PortfolioSnapshot, RiskAction, RiskDecision, Signal, SignalDirection,
)
from src.risk.circuit_breaker import DrawdownCircuitBreaker
from src.risk.models import RiskContext, VolatilityRegime
from src.risk.protocols import PositionSizer

REGIME_LIMITS = {
    VolatilityRegime.LOW: {
        "max_position_pct": 3.0,
        "stop_loss_pct": 4.0,
        "max_open_positions": 12,
        "daily_loss_limit_pct": 4.0,
    },
    VolatilityRegime.MEDIUM: {
        "max_position_pct": 2.0,
        "stop_loss_pct": 5.0,
        "max_open_positions": 8,
        "daily_loss_limit_pct": 3.0,
    },
    VolatilityRegime.HIGH: {
        "max_position_pct": 1.0,
        "stop_loss_pct": 8.0,
        "max_open_positions": 4,
        "daily_loss_limit_pct": 2.0,
    },
}


class RiskManager:
    def __init__(
        self,
        settings: RiskSettings,
        position_sizer: PositionSizer | None = None,
        circuit_breaker: DrawdownCircuitBreaker | None = None,
    ):
        self._settings = settings
        self._daily_pnl = Decimal("0")
        self._position_sizer = position_sizer
        self._circuit_breaker = circuit_breaker

    def record_daily_pnl(self, pnl: Decimal) -> None:
        self._daily_pnl = pnl

    def reset_daily_pnl(self) -> None:
        self._daily_pnl = Decimal("0")

    def update_circuit_breaker(self, portfolio_value: Decimal, now: datetime) -> None:
        if self._circuit_breaker:
            self._circuit_breaker.update(portfolio_value, now)

    async def evaluate_trade(
        self,
        signal: Signal,
        portfolio: PortfolioSnapshot,
        risk_context: RiskContext | None = None,
    ) -> RiskDecision:
        # 1. Circuit breaker check
        if self._circuit_breaker is not None:
            if self._circuit_breaker.is_tripped(portfolio.total_value, signal.timestamp):
                return RiskDecision(
                    action=RiskAction.VETO,
                    reason="Circuit breaker tripped: drawdown exceeded threshold",
                )

        # Determine effective limits (regime-adjusted or static)
        if risk_context is not None:
            regime_limits = REGIME_LIMITS[risk_context.regime]
            effective_daily_loss_limit = regime_limits["daily_loss_limit_pct"]
            effective_max_positions = regime_limits["max_open_positions"]
        else:
            effective_daily_loss_limit = self._settings.daily_loss_limit_pct
            effective_max_positions = self._settings.max_open_positions

        # 2. Check daily loss limit
        if portfolio.total_value > 0:
            daily_loss_pct = abs(self._daily_pnl) / portfolio.total_value * 100
            if self._daily_pnl < 0 and daily_loss_pct >= effective_daily_loss_limit:
                return RiskDecision(
                    action=RiskAction.VETO,
                    reason=f"Daily loss limit exceeded: {daily_loss_pct:.1f}% "
                           f"(limit: {effective_daily_loss_limit}%)",
                )

        # 3. Check max open positions
        if len(portfolio.positions) >= effective_max_positions:
            existing_symbols = {p.symbol for p in portfolio.positions}
            if signal.symbol not in existing_symbols:
                return RiskDecision(
                    action=RiskAction.VETO,
                    reason=f"Max open positions reached: {len(portfolio.positions)} "
                           f"(limit: {effective_max_positions})",
                )

        # 4. Correlation check (only when risk_context is provided)
        if risk_context is not None:
            max_corr = self._settings.max_correlation
            resize_threshold = max_corr * 0.7
            worst_correlation = 0.0
            worst_pair = ""

            for position in portfolio.positions:
                corr = risk_context.get_correlation(signal.symbol, position.symbol)
                abs_corr = abs(corr)
                if abs_corr > worst_correlation:
                    worst_correlation = abs_corr
                    worst_pair = position.symbol

            if worst_correlation > max_corr:
                return RiskDecision(
                    action=RiskAction.VETO,
                    reason=f"High correlation with {worst_pair}: "
                           f"{worst_correlation:.2f} (limit: {max_corr})",
                )

            if worst_correlation > resize_threshold:
                multiplier = Decimal(str(1 - worst_correlation / max_corr))
                return RiskDecision(
                    action=RiskAction.RESIZE,
                    reason=f"Moderate correlation with {worst_pair}: "
                           f"{worst_correlation:.2f}, reducing size",
                    size_multiplier=multiplier,
                )

        # 5. Approve
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
