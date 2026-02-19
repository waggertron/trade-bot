"""Portfolio-level simulation logic."""
from __future__ import annotations

import math

from src.simulation.models import PortfolioMetrics, SimulationConfig


class PortfolioSimulator:
    """Manages portfolio-level simulation: allocation, equity curves, and metrics.

    This is a mutable service class, not a data model.
    """

    def __init__(self, config: SimulationConfig) -> None:
        self._config = config
        self._weights = self._compute_weights()

    # ------------------------------------------------------------------
    # Weight computation
    # ------------------------------------------------------------------

    def _compute_weights(self) -> dict[str, float]:
        """Compute per-stock weights from the allocation config."""
        if self._config.allocation.mode == "equal_weight":
            n = len(self._config.stocks)
            return {s: 1.0 / n for s in self._config.stocks}
        # custom mode
        return dict(self._config.allocation.weights)

    @property
    def weights(self) -> dict[str, float]:
        """Read-only access to the computed weights."""
        return dict(self._weights)

    # ------------------------------------------------------------------
    # Capital allocation
    # ------------------------------------------------------------------

    def get_stock_balance(self, symbol: str) -> float:
        """Return the initial capital allocated to *symbol*."""
        return self._config.initial_balance * self._weights[symbol]

    # ------------------------------------------------------------------
    # Equity curve
    # ------------------------------------------------------------------

    def build_portfolio_equity_curve(
        self, stock_curves: dict[str, list[float]]
    ) -> list[float]:
        """Combine per-stock equity curves into a single portfolio curve.

        Each stock curve is normalised by its starting value and then scaled
        by its allocated capital.  Stocks with empty curves or a zero starting
        value are silently skipped.
        """
        if not stock_curves:
            return []

        # Filter usable curves
        usable: list[tuple[str, list[float]]] = []
        for symbol, curve in stock_curves.items():
            if curve and curve[0] != 0:
                usable.append((symbol, curve))

        if not usable:
            return []

        min_len = min(len(curve) for _, curve in usable)

        portfolio: list[float] = []
        for i in range(min_len):
            value = 0.0
            for symbol, curve in usable:
                allocated = self._config.initial_balance * self._weights[symbol]
                value += allocated * (curve[i] / curve[0])
            portfolio.append(value)

        return portfolio

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def compute_portfolio_metrics(
        self, equity_curve: list[float], total_trades: int
    ) -> PortfolioMetrics:
        """Derive portfolio-level performance metrics from an equity curve."""
        initial = equity_curve[0] if equity_curve else 0.0
        final = equity_curve[-1] if equity_curve else 0.0

        # Daily returns
        daily_returns: list[float] = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]
            if prev != 0:
                daily_returns.append((equity_curve[i] - prev) / prev)

        # Total return
        total_return_pct = ((final - initial) / initial * 100) if initial else 0.0

        # Max drawdown (percentage)
        max_drawdown = self._max_drawdown(equity_curve)

        # Sharpe ratio (annualised)
        sharpe_ratio = self._sharpe(daily_returns)

        # Sortino ratio (annualised)
        sortino_ratio = self._sortino(daily_returns)

        # Calmar ratio
        calmar_ratio = self._calmar(total_return_pct, max_drawdown, len(daily_returns))

        return PortfolioMetrics(
            initial_balance=self._config.initial_balance,
            final_value=final,
            total_return_pct=total_return_pct,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            total_trades=total_trades,
            equity_curve=list(equity_curve),
            daily_returns=daily_returns,
            rebalance_dates=[],
        )

    # ------------------------------------------------------------------
    # Rebalancing
    # ------------------------------------------------------------------

    def should_rebalance(self, day_index: int, total_days: int) -> bool:
        """Return whether the portfolio should be rebalanced on *day_index*."""
        if day_index == 0:
            return False

        freq = self._config.rebalance.frequency
        if freq == "none":
            return False
        if freq == "daily":
            return True
        if freq == "weekly":
            return day_index % 5 == 0
        if freq == "monthly":
            return day_index % 21 == 0
        return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _max_drawdown(curve: list[float]) -> float:
        """Peak-to-trough drawdown as a percentage."""
        if len(curve) < 2:
            return 0.0
        peak = curve[0]
        max_dd = 0.0
        for val in curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100 if peak else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @staticmethod
    def _sharpe(daily_returns: list[float]) -> float:
        """Annualised Sharpe ratio."""
        if not daily_returns:
            return 0.0
        mean_r = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)
        std_r = math.sqrt(variance)
        if std_r == 0:
            return 0.0
        return mean_r / std_r * math.sqrt(252)

    @staticmethod
    def _sortino(daily_returns: list[float]) -> float:
        """Annualised Sortino ratio."""
        if not daily_returns:
            return 0.0
        mean_r = sum(daily_returns) / len(daily_returns)
        neg = [r for r in daily_returns if r < 0]
        if not neg:
            return 0.0
        variance = sum(r**2 for r in neg) / len(neg)
        std_neg = math.sqrt(variance)
        if std_neg == 0:
            return 0.0
        return mean_r / std_neg * math.sqrt(252)

    @staticmethod
    def _calmar(
        total_return_pct: float, max_drawdown: float, n_daily: int
    ) -> float:
        """Calmar ratio: annualised return / max drawdown."""
        if max_drawdown == 0 or n_daily == 0:
            return 0.0
        annualised = total_return_pct * (252 / n_daily)
        return annualised / max_drawdown
