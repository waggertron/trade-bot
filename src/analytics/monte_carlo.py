"""Monte Carlo simulation of trade-sequence risk via random shuffling."""

from __future__ import annotations

import random

from src.analytics.models import MonteCarloResult, Trade


class MonteCarloSimulator:
    """Shuffle trade order many times to assess how lucky/unlucky the actual sequence was."""

    def __init__(self, n_simulations: int = 1000, seed: int | None = None) -> None:
        self._n_simulations = n_simulations
        self._seed = seed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate(self, trades: list[Trade], initial_cash: float) -> MonteCarloResult:
        """Run the Monte Carlo simulation and return aggregated results."""
        if not trades:
            return MonteCarloResult(
                actual_final_value=initial_cash,
                percentile=50.0,
                median_simulated=initial_cash,
                p5_simulated=initial_cash,
                p95_simulated=initial_cash,
                worst_drawdown_p95=0.0,
                n_simulations=self._n_simulations,
            )

        # Actual equity curve
        actual_equity = self._build_equity(trades, initial_cash)
        actual_final = actual_equity[-1]

        # Seeded random instance for reproducibility
        rng = random.Random(self._seed)

        simulated_finals: list[float] = []
        simulated_drawdowns: list[float] = []

        for _ in range(self._n_simulations):
            shuffled = list(trades)
            rng.shuffle(shuffled)
            equity = self._build_equity(shuffled, initial_cash)
            simulated_finals.append(equity[-1])
            simulated_drawdowns.append(self._max_drawdown(equity))

        # Percentile: fraction of simulated finals strictly less than actual
        count_below = sum(1 for f in simulated_finals if f < actual_final)
        percentile = count_below / self._n_simulations * 100.0

        sorted_finals = sorted(simulated_finals)
        sorted_drawdowns = sorted(simulated_drawdowns)

        return MonteCarloResult(
            actual_final_value=actual_final,
            percentile=percentile,
            median_simulated=self._percentile(sorted_finals, 50.0),
            p5_simulated=self._percentile(sorted_finals, 5.0),
            p95_simulated=self._percentile(sorted_finals, 95.0),
            worst_drawdown_p95=self._percentile(sorted_drawdowns, 95.0),
            n_simulations=self._n_simulations,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_equity(trades: list[Trade], initial_cash: float) -> list[float]:
        """Build a cumulative equity curve from an ordered list of trades."""
        equity = [initial_cash]
        running = initial_cash
        for trade in trades:
            running += trade.pnl
            equity.append(running)
        return equity

    @staticmethod
    def _max_drawdown(equity: list[float]) -> float:
        """Return the maximum peak-to-trough drawdown as a fraction (0 to 1)."""
        if not equity:
            return 0.0
        peak = equity[0]
        max_dd = 0.0
        for value in equity:
            if value > peak:
                peak = value
            if peak > 0:
                dd = (peak - value) / peak
                if dd > max_dd:
                    max_dd = dd
        return max_dd

    @staticmethod
    def _percentile(sorted_values: list[float], pct: float) -> float:
        """Return the value at the given percentile from a pre-sorted list."""
        idx = int(len(sorted_values) * pct / 100)
        idx = min(idx, len(sorted_values) - 1)
        return sorted_values[idx]
