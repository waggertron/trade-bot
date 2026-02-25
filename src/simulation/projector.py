"""Monte Carlo price path projector using geometric Brownian motion."""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


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
        drift = mu - 0.5 * sigma**2
        shocks = self._rng.normal(0, 1, size=(self._n_paths, days_forward))

        log_paths = drift + sigma * shocks
        log_paths = np.cumsum(log_paths, axis=1)
        paths = last_price * np.exp(log_paths)

        return paths

    def generate_correlated_portfolio_paths(
        self,
        historical_prices: dict[str, list[float]],
        days_forward: int,
        weights: dict[str, float],
        initial_balance: float,
    ) -> tuple[np.ndarray, list[list[float]]]:
        """Generate correlated portfolio paths using Cholesky-decomposed GBM.

        Returns (portfolio_paths, correlation_matrix) where:
        - portfolio_paths: ndarray of shape (n_paths, days_forward)
        - correlation_matrix: the computed return correlation as list[list[float]]
        """
        symbols = list(historical_prices.keys())
        n_stocks = len(symbols)

        if n_stocks == 0:
            return np.empty((self._n_paths, 0)), []

        # 1. Compute log returns per stock
        all_log_returns: list[np.ndarray] = []
        for sym in symbols:
            prices = np.array(historical_prices[sym])
            log_ret = np.diff(np.log(prices))
            all_log_returns.append(log_ret)

        # 2. Align returns to minimum common length
        min_len = min(len(lr) for lr in all_log_returns)
        aligned = np.column_stack([lr[:min_len] for lr in all_log_returns])
        # aligned shape: (min_len, n_stocks)

        # 3. Build return correlation matrix
        corr_matrix = np.corrcoef(aligned, rowvar=False)
        # Handle single-stock case where corrcoef returns a scalar
        if corr_matrix.ndim == 0:
            corr_matrix = np.array([[1.0]])

        # 4. Cholesky decomposition (with fallback)
        try:
            chol = np.linalg.cholesky(corr_matrix)
        except np.linalg.LinAlgError:
            logger.warning(
                "Cholesky decomposition failed (non-positive-definite matrix). "
                "Falling back to uncorrelated simulation."
            )
            chol = np.eye(n_stocks)

        # 5. Generate independent normal shocks: (n_paths, days_forward, n_stocks)
        independent_shocks = self._rng.normal(
            0,
            1,
            size=(self._n_paths, days_forward, n_stocks),
        )

        # 6. Apply Cholesky factor to correlate shocks
        # correlated[p, d, :] = chol @ independent[p, d, :]
        correlated_shocks = np.einsum("ij,pdj->pdi", chol, independent_shocks)

        # 7. Per-stock GBM parameters and price paths
        mus = []
        sigmas = []
        last_prices = []
        for i, sym in enumerate(symbols):
            lr_aligned = aligned[:, i]
            mu_i = float(np.mean(lr_aligned))
            sigma_i = float(np.std(lr_aligned))
            if sigma_i == 0:
                sigma_i = 1e-10
            mus.append(mu_i)
            sigmas.append(sigma_i)
            last_prices.append(historical_prices[sym][-1])

        # Build per-stock price paths: shape (n_paths, days_forward, n_stocks)
        stock_price_paths = np.empty((self._n_paths, days_forward, n_stocks))
        for i in range(n_stocks):
            drift = mus[i] - 0.5 * sigmas[i] ** 2
            log_increments = drift + sigmas[i] * correlated_shocks[:, :, i]
            cumulative = np.cumsum(log_increments, axis=1)
            stock_price_paths[:, :, i] = last_prices[i] * np.exp(cumulative)

        # 8. Convert to portfolio value
        # shares_s = (initial_balance * weight_s) / last_price_s
        shares = np.array(
            [(initial_balance * weights[sym]) / last_prices[i] for i, sym in enumerate(symbols)]
        )

        # portfolio_value[path, day] = sum(shares_s * price_path_s[path, day])
        portfolio_paths = np.einsum("pds,s->pd", stock_price_paths, shares)

        return portfolio_paths, corr_matrix.tolist()

    def summarize_portfolio_paths(
        self,
        portfolio_paths: np.ndarray,
        initial_balance: float,
    ) -> dict[str, float | int]:
        """Compute summary statistics from portfolio-level paths.

        Unlike ``summarize``, the input paths are already in dollar values
        (not raw price paths), so no shares conversion is needed.
        """
        final_values = portfolio_paths[:, -1]

        median_final = float(np.median(final_values))
        p5_final = float(np.percentile(final_values, 5))
        p95_final = float(np.percentile(final_values, 95))

        # Compute drawdowns per path (paths are already in portfolio $ values)
        cummax = np.maximum.accumulate(portfolio_paths, axis=1)
        drawdowns = (cummax - portfolio_paths) / np.where(cummax > 0, cummax, 1)
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
            "n_paths": portfolio_paths.shape[0],
        }

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
