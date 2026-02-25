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
    ) -> tuple[list[float], list[int]]:
        """Combine per-stock equity curves into a single portfolio curve.

        Each stock curve is normalised by its starting value and then scaled
        by its allocated capital.  On rebalance days, per-stock allocations
        are reset to target weights based on current portfolio value.

        Returns a tuple of (equity_curve, rebalance_day_indices).
        """
        if not stock_curves:
            return [], []

        # Filter usable curves
        usable: list[tuple[str, list[float]]] = []
        for symbol, curve in stock_curves.items():
            if symbol not in self._weights:
                continue
            if curve and curve[0] != 0:
                usable.append((symbol, curve))

        if not usable:
            return [], []

        min_len = min(len(curve) for _, curve in usable)
        initial_balance = self._config.initial_balance

        # Mutable per-stock allocations and base prices
        allocated = {sym: initial_balance * self._weights[sym] for sym, _ in usable}
        base = {sym: curve[0] for sym, curve in usable}
        rebalance_days: list[int] = []

        portfolio: list[float] = []
        for i in range(min_len):
            value = sum(allocated[sym] * (curve[i] / base[sym]) for sym, curve in usable)
            portfolio.append(value)

            if self.should_rebalance(i, min_len):
                rebalance_days.append(i)
                for sym, curve in usable:
                    allocated[sym] = value * self._weights[sym]
                    base[sym] = curve[i]

        return portfolio, rebalance_days

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def compute_portfolio_metrics(
        self,
        equity_curve: list[float],
        total_trades: int,
        *,
        rebalance_days: list[int] | None = None,
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
            rebalance_dates=rebalance_days or [],
        )

    # ------------------------------------------------------------------
    # Rebalancing
    # ------------------------------------------------------------------

    def should_rebalance(self, day_index: int, total_days: int) -> bool:
        """Return whether the portfolio should be rebalanced on *day_index*."""
        # total_days reserved for threshold-based rebalancing
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
            # No downside risk — return capped high value
            mean_r = sum(daily_returns) / len(daily_returns) if daily_returns else 0.0
            return 99.99 if mean_r > 0 else 0.0
        variance = sum(r**2 for r in neg) / len(neg)
        std_neg = math.sqrt(variance)
        if std_neg == 0:
            return 0.0
        return mean_r / std_neg * math.sqrt(252)

    @staticmethod
    def _calmar(total_return_pct: float, max_drawdown: float, n_daily: int) -> float:
        """Calmar ratio: annualised return / max drawdown."""
        if max_drawdown == 0 or n_daily == 0:
            return 0.0
        annualised = total_return_pct * (252 / n_daily)
        return annualised / max_drawdown
