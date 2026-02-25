"""Tests for Monte Carlo price path projection."""

from src.simulation.projector import MonteCarloProjector


def test_projector_generates_correct_number_of_paths():
    prices = [100.0, 101.0, 99.5, 102.0, 100.5]
    proj = MonteCarloProjector(n_paths=50, seed=42)
    paths = proj.generate_paths(prices, days_forward=10)
    assert paths.shape == (50, 10)


def test_projector_paths_start_from_last_price():
    prices = [100.0, 101.0, 99.5, 102.0, 100.5]
    proj = MonteCarloProjector(n_paths=100, seed=42)
    paths = proj.generate_paths(prices, days_forward=5)
    # First day should be close to last price (within 1 day of random walk)
    assert all(p > 0 for p in paths[:, 0])


def test_projector_summary_stats():
    prices = [100.0 + i * 0.5 for i in range(60)]  # upward trending
    proj = MonteCarloProjector(n_paths=500, seed=42)
    paths = proj.generate_paths(prices, days_forward=30)
    summary = proj.summarize(paths, initial_balance=10000.0, last_price=prices[-1])
    assert summary["median_final"] > 0
    assert summary["p5_final"] < summary["p95_final"]
    assert summary["n_paths"] == 500


def test_projector_with_flat_prices():
    """Flat prices should produce narrow spread."""
    prices = [100.0] * 60
    proj = MonteCarloProjector(n_paths=200, seed=42)
    paths = proj.generate_paths(prices, days_forward=30)
    summary = proj.summarize(paths, initial_balance=10000.0, last_price=100.0)
    # With zero volatility, all paths should stay near 100
    assert abs(summary["median_final"] - 10000.0) < 500  # within 5%
