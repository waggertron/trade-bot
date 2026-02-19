"""Passive benchmark simulators (buy-and-hold, monthly DCA)."""
from __future__ import annotations

import math

from src.data.providers.base import OHLCBar
from src.simulation.models import BenchmarkResult


class BenchmarkSimulator:
    """Compute passive benchmark returns for comparison against active strategies."""

    def buy_and_hold(self, bars: list[OHLCBar], initial_balance: float) -> BenchmarkResult:
        """Simulate buying at first bar close, holding through all bars."""
        if not bars:
            raise ValueError("bars must not be empty")

        prices = [float(b.close) for b in bars]
        buy_price = prices[0]
        shares = initial_balance / buy_price

        equity_curve = [shares * p for p in prices]
        daily_returns = self._daily_returns(equity_curve)

        return BenchmarkResult(
            name="SPY Buy-and-Hold",
            initial_balance=initial_balance,
            final_value=equity_curve[-1],
            return_pct=(equity_curve[-1] - initial_balance) / initial_balance * 100,
            max_drawdown=self._max_drawdown(equity_curve),
            sharpe_ratio=self._sharpe(daily_returns),
            equity_curve=equity_curve,
        )

    def monthly_dca(self, bars: list[OHLCBar], initial_balance: float) -> BenchmarkResult:
        """Simulate monthly dollar-cost averaging over the bar period."""
        if not bars:
            raise ValueError("bars must not be empty")

        prices = [float(b.close) for b in bars]
        trading_days_per_month = 21

        # Determine number of monthly buy points
        n_months = max(1, len(prices) // trading_days_per_month)
        monthly_amount = initial_balance / n_months

        # Track shares accumulated and equity curve
        total_shares = 0.0
        cash_remaining = initial_balance
        equity_curve: list[float] = []

        for i, price in enumerate(prices):
            # Buy at the first bar of each month
            if i % trading_days_per_month == 0 and cash_remaining >= monthly_amount * 0.99:
                invest = min(monthly_amount, cash_remaining)
                total_shares += invest / price
                cash_remaining -= invest

            equity_curve.append(total_shares * price + cash_remaining)

        daily_returns = self._daily_returns(equity_curve)

        return BenchmarkResult(
            name="SPY Monthly DCA",
            initial_balance=initial_balance,
            final_value=equity_curve[-1],
            return_pct=(equity_curve[-1] - initial_balance) / initial_balance * 100,
            max_drawdown=self._max_drawdown(equity_curve),
            sharpe_ratio=self._sharpe(daily_returns),
            equity_curve=equity_curve,
        )

    @staticmethod
    def _daily_returns(curve: list[float]) -> list[float]:
        returns = []
        for i in range(1, len(curve)):
            prev = curve[i - 1]
            if prev != 0:
                returns.append((curve[i] - prev) / prev)
        return returns

    @staticmethod
    def _max_drawdown(curve: list[float]) -> float:
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
        if not daily_returns:
            return 0.0
        mean_r = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)
        std_r = math.sqrt(variance)
        if std_r == 0:
            return 0.0
        return mean_r / std_r * math.sqrt(252)
