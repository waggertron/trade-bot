"""Tests for correlated Monte Carlo portfolio projection."""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from src.simulation.projector import MonteCarloProjector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prices(n: int, start: float = 100.0, drift: float = 0.5) -> list[float]:
    """Create a simple price series with upward drift."""
    return [start + i * drift for i in range(n)]


def _make_two_stock_prices(n: int = 60) -> dict[str, list[float]]:
    """Two correlated stock price series."""
    return {
        "AAPL": _make_prices(n, start=150.0, drift=0.3),
        "GOOG": _make_prices(n, start=2800.0, drift=2.0),
    }


# ---------------------------------------------------------------------------
# Test 1: Shape
# ---------------------------------------------------------------------------

def test_correlated_paths_shape():
    """2 stocks, 100 paths, 30 days -> portfolio_paths shape is (100, 30)."""
    projector = MonteCarloProjector(n_paths=100, seed=42)
    prices = _make_two_stock_prices(60)
    weights = {"AAPL": 0.5, "GOOG": 0.5}

    portfolio_paths, corr_matrix = projector.generate_correlated_portfolio_paths(
        historical_prices=prices,
        days_forward=30,
        weights=weights,
        initial_balance=10000.0,
    )

    assert portfolio_paths.shape == (100, 30)
    assert isinstance(corr_matrix, list)
    assert len(corr_matrix) == 2
    assert len(corr_matrix[0]) == 2


# ---------------------------------------------------------------------------
# Test 2: Positive values
# ---------------------------------------------------------------------------

def test_correlated_paths_positive_values():
    """All portfolio values should be positive (GBM produces positive prices)."""
    projector = MonteCarloProjector(n_paths=200, seed=123)
    prices = _make_two_stock_prices(60)
    weights = {"AAPL": 0.6, "GOOG": 0.4}

    portfolio_paths, _ = projector.generate_correlated_portfolio_paths(
        historical_prices=prices,
        days_forward=30,
        weights=weights,
        initial_balance=10000.0,
    )

    assert np.all(portfolio_paths > 0), "All portfolio values should be positive"


# ---------------------------------------------------------------------------
# Test 3: Correlation matrix diagonal
# ---------------------------------------------------------------------------

def test_correlation_matrix_diagonal():
    """Diagonal entries of correlation matrix should be ~1.0."""
    projector = MonteCarloProjector(n_paths=50, seed=42)
    prices = {
        "AAPL": _make_prices(60, start=150.0, drift=0.3),
        "GOOG": _make_prices(60, start=2800.0, drift=2.0),
        "MSFT": _make_prices(60, start=300.0, drift=0.8),
    }
    weights = {"AAPL": 0.4, "GOOG": 0.3, "MSFT": 0.3}

    _, corr_matrix = projector.generate_correlated_portfolio_paths(
        historical_prices=prices,
        days_forward=10,
        weights=weights,
        initial_balance=10000.0,
    )

    assert len(corr_matrix) == 3
    for i in range(3):
        assert corr_matrix[i][i] == pytest.approx(1.0, abs=1e-10), (
            f"Diagonal entry [{i}][{i}] should be 1.0, got {corr_matrix[i][i]}"
        )


# ---------------------------------------------------------------------------
# Test 4: Single stock matches uncorrelated
# ---------------------------------------------------------------------------

def test_single_stock_matches_uncorrelated():
    """With 1 stock and weight 1.0, correlated MC should produce same paths as uncorrelated.

    Both use the same seed, so the RNG states should produce identical shocks.
    For a single stock, the Cholesky factor is [[1.0]] (identity), so the
    correlated shocks equal the independent shocks -- the portfolio-value paths
    should match the single-stock value paths from the uncorrelated projector.
    """
    prices_list = _make_prices(60, start=150.0, drift=0.3)
    initial_balance = 10000.0
    days = 20

    # Uncorrelated single-stock projection
    proj_uncorr = MonteCarloProjector(n_paths=100, seed=99)
    uncorr_paths = proj_uncorr.generate_paths(prices_list, days)
    last_price = prices_list[-1]
    shares = initial_balance / last_price
    uncorr_portfolio = uncorr_paths * shares  # shape (100, 20)

    # Correlated single-stock projection (same seed)
    proj_corr = MonteCarloProjector(n_paths=100, seed=99)
    corr_portfolio, corr_matrix = proj_corr.generate_correlated_portfolio_paths(
        historical_prices={"AAPL": prices_list},
        days_forward=days,
        weights={"AAPL": 1.0},
        initial_balance=initial_balance,
    )

    # Correlation matrix for single stock is [[1.0]]
    assert corr_matrix == [[pytest.approx(1.0)]]

    # Portfolio values should be identical (same RNG seed, same algorithm)
    np.testing.assert_allclose(corr_portfolio, uncorr_portfolio, rtol=1e-10)


# ---------------------------------------------------------------------------
# Test 5: Cholesky fallback
# ---------------------------------------------------------------------------

def test_cholesky_fallback():
    """When Cholesky decomposition fails, fall back to uncorrelated simulation.

    Mock np.linalg.cholesky to raise LinAlgError and verify the method
    still returns valid results using the identity matrix fallback.
    """
    projector = MonteCarloProjector(n_paths=50, seed=42)
    prices = _make_two_stock_prices(60)
    weights = {"AAPL": 0.5, "GOOG": 0.5}

    with patch("numpy.linalg.cholesky", side_effect=np.linalg.LinAlgError("not positive definite")):
        portfolio_paths, corr_matrix = projector.generate_correlated_portfolio_paths(
            historical_prices=prices,
            days_forward=20,
            weights=weights,
            initial_balance=10000.0,
        )

    # Should still produce valid paths
    assert portfolio_paths.shape == (50, 20)
    assert np.all(portfolio_paths > 0), "Fallback paths should be positive"

    # Correlation matrix should still be returned (computed before Cholesky)
    assert len(corr_matrix) == 2
    assert len(corr_matrix[0]) == 2


# ---------------------------------------------------------------------------
# Test 6: Summarize portfolio paths
# ---------------------------------------------------------------------------

def test_summarize_portfolio_paths():
    """Verify summary statistics from known portfolio paths.

    P5 < median < P95, drawdown >= 0, correct n_paths.
    """
    projector = MonteCarloProjector(n_paths=500, seed=42)
    prices = _make_two_stock_prices(60)
    weights = {"AAPL": 0.5, "GOOG": 0.5}
    initial_balance = 10000.0

    portfolio_paths, _ = projector.generate_correlated_portfolio_paths(
        historical_prices=prices,
        days_forward=30,
        weights=weights,
        initial_balance=initial_balance,
    )

    summary = projector.summarize_portfolio_paths(portfolio_paths, initial_balance)

    # Percentile ordering
    assert summary["p5_final"] < summary["median_final"] < summary["p95_final"]
    assert summary["p5_return_pct"] < summary["median_return_pct"] < summary["p95_return_pct"]

    # Drawdown must be non-negative
    assert summary["worst_drawdown_p95"] >= 0

    # n_paths
    assert summary["n_paths"] == 500

    # Return percentages should be relative to initial_balance
    expected_median_return = (summary["median_final"] - initial_balance) / initial_balance * 100
    assert summary["median_return_pct"] == pytest.approx(expected_median_return, rel=1e-10)


# ---------------------------------------------------------------------------
# Test 7: Engine integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_engine_portfolio_monte_carlo():
    """Full engine test: portfolio_mode=True produces portfolio_monte_carlo.

    Verifies that portfolio_monte_carlo is not None, has a correlation matrix,
    and has valid numeric fields.
    """
    from unittest.mock import AsyncMock

    from src.core.config import RiskLevel
    from src.data.providers.base import OHLCBar
    from src.simulation.engine import SimulationEngine
    from src.simulation.models import SimulationConfig

    def _make_bars(n: int, start_price: float = 100.0) -> list[OHLCBar]:
        bars = []
        base_ts = 1700000000
        for i in range(n):
            price = start_price + i * 0.5
            bars.append(OHLCBar(
                timestamp=base_ts + i * 86400,
                open=str(price - 0.2),
                high=str(price + 1.0),
                low=str(price - 1.0),
                close=str(price),
                volume=str(1000000),
                source="yfinance",
            ))
        return bars

    config = SimulationConfig(
        stocks=["AAPL", "GOOG"],
        initial_balance=20000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=50,
        portfolio_mode=True,
    )
    engine = SimulationEngine(config)
    bars = _make_bars(90)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert report.status == "completed"
    result = report.risk_level_results["moderate"]

    # Portfolio Monte Carlo should be populated
    pmc = result.portfolio_monte_carlo
    assert pmc is not None, "portfolio_monte_carlo should not be None in portfolio mode"

    # Correlation matrix should be 2x2 for 2 stocks
    assert len(pmc.correlation_matrix) == 2
    assert len(pmc.correlation_matrix[0]) == 2

    # Numeric validity
    assert pmc.n_paths == 50
    assert pmc.median_final > 0
    assert pmc.p5_final < pmc.p95_final
    assert pmc.worst_drawdown_p95 >= 0
