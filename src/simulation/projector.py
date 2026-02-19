"""Monte Carlo price path projector using geometric Brownian motion."""
from __future__ import annotations

import numpy as np


class MonteCarloProjector:
    """Generate synthetic forward price paths from historical returns."""

    def __init__(self, n_paths: int = 1000, seed: int | None = None) -> None:
        self._n_paths = n_paths
        self._rng = np.random.default_rng(seed)

    def generate_paths(
        self,
        historical_prices: list[float],
        days_forward: int,
    ) -> np.ndarray:
        """Generate price paths using geometric Brownian motion.

        Returns ndarray of shape (n_paths, days_forward).
        """
        prices = np.array(historical_prices)
        log_returns = np.diff(np.log(prices))

        mu = float(np.mean(log_returns))
        sigma = float(np.std(log_returns))
        if sigma == 0:
            sigma = 1e-10  # avoid division by zero

        last_price = prices[-1]

        # GBM: S(t+1) = S(t) * exp((mu - sigma^2/2) + sigma * Z)
        drift = mu - 0.5 * sigma ** 2
        shocks = self._rng.normal(0, 1, size=(self._n_paths, days_forward))

        log_paths = drift + sigma * shocks
        log_paths = np.cumsum(log_paths, axis=1)
        paths = last_price * np.exp(log_paths)

        return paths

    def summarize(
        self,
        paths: np.ndarray,
        initial_balance: float,
        last_price: float,
    ) -> dict[str, float | int]:
        """Compute summary statistics from projected paths.

        Converts price paths to portfolio value using shares = balance / last_price.
        """
        if last_price <= 0:
            return {
                "median_final": initial_balance,
                "p5_final": initial_balance,
                "p95_final": initial_balance,
                "median_return_pct": 0.0,
                "p5_return_pct": 0.0,
                "p95_return_pct": 0.0,
                "worst_drawdown_p95": 0.0,
                "n_paths": self._n_paths,
            }

        shares = initial_balance / last_price
        final_values = paths[:, -1] * shares

        median_final = float(np.median(final_values))
        p5_final = float(np.percentile(final_values, 5))
        p95_final = float(np.percentile(final_values, 95))

        # Compute drawdowns per path
        value_paths = paths * shares
        cummax = np.maximum.accumulate(value_paths, axis=1)
        drawdowns = (cummax - value_paths) / np.where(cummax > 0, cummax, 1)
        max_drawdowns = np.max(drawdowns, axis=1)
        worst_dd_p95 = float(np.percentile(max_drawdowns, 95))

        return {
            "median_final": median_final,
            "p5_final": p5_final,
            "p95_final": p95_final,
            "median_return_pct": (median_final - initial_balance) / initial_balance * 100,
            "p5_return_pct": (p5_final - initial_balance) / initial_balance * 100,
            "p95_return_pct": (p95_final - initial_balance) / initial_balance * 100,
            "worst_drawdown_p95": worst_dd_p95 * 100,
            "n_paths": self._n_paths,
        }
