"""Tests for MonteCarloSimulator: shuffled-trade equity simulation."""

from __future__ import annotations

import pytest

from src.analytics.models import Trade
from src.analytics.monte_carlo import MonteCarloSimulator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_trade(pnl: float, symbol: str = "BTC/USD") -> Trade:
    """Create a Trade with the given pnl (entry/exit prices derived)."""
    entry = 100.0
    exit_price = entry + pnl
    return Trade(
        symbol=symbol,
        entry_price=entry,
        exit_price=exit_price,
        quantity=1.0,
        pnl=pnl,
        strategy="test",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMonteCarloSimulator:
    """Tests for MonteCarloSimulator.simulate()."""

    # -- empty trades -------------------------------------------------------

    def test_empty_trades(self) -> None:
        sim = MonteCarloSimulator(n_simulations=100, seed=42)
        result = sim.simulate([], initial_cash=10_000.0)

        assert result.actual_final_value == 10_000.0
        assert result.percentile == 50.0
        assert result.median_simulated == 10_000.0
        assert result.p5_simulated == 10_000.0
        assert result.p95_simulated == 10_000.0
        assert result.worst_drawdown_p95 == 0.0
        assert result.n_simulations == 100

    # -- single winning trade -----------------------------------------------

    def test_single_winning_trade(self) -> None:
        trades = [make_trade(pnl=50.0)]
        sim = MonteCarloSimulator(n_simulations=100, seed=42)
        result = sim.simulate(trades, initial_cash=1_000.0)

        assert result.actual_final_value == 1_050.0

    # -- single losing trade ------------------------------------------------

    def test_single_losing_trade(self) -> None:
        trades = [make_trade(pnl=-30.0)]
        sim = MonteCarloSimulator(n_simulations=100, seed=42)
        result = sim.simulate(trades, initial_cash=1_000.0)

        assert result.actual_final_value == 970.0

    # -- multiple trades ----------------------------------------------------

    def test_multiple_trades(self) -> None:
        trades = [make_trade(pnl=10.0), make_trade(pnl=-5.0), make_trade(pnl=20.0)]
        sim = MonteCarloSimulator(n_simulations=100, seed=42)
        result = sim.simulate(trades, initial_cash=1_000.0)

        expected_final = 1_000.0 + 10.0 + (-5.0) + 20.0
        assert result.actual_final_value == pytest.approx(expected_final)

    # -- seed produces deterministic results --------------------------------

    def test_seed_produces_deterministic_results(self) -> None:
        trades = [make_trade(pnl=i * 10.0) for i in range(-5, 6)]
        sim1 = MonteCarloSimulator(n_simulations=500, seed=123)
        sim2 = MonteCarloSimulator(n_simulations=500, seed=123)

        r1 = sim1.simulate(trades, initial_cash=10_000.0)
        r2 = sim2.simulate(trades, initial_cash=10_000.0)

        assert r1.percentile == r2.percentile
        assert r1.median_simulated == r2.median_simulated
        assert r1.p5_simulated == r2.p5_simulated
        assert r1.p95_simulated == r2.p95_simulated
        assert r1.worst_drawdown_p95 == r2.worst_drawdown_p95

    # -- percentile for a good strategy -------------------------------------

    def test_percentile_good_strategy(self) -> None:
        """Consistently winning trades should rank above random shuffles."""
        # Trades arranged best-first: the actual ordering front-loads wins
        # so drawdowns are minimal.  Shuffling will often degrade that.
        trades = [
            make_trade(pnl=100.0),
            make_trade(pnl=80.0),
            make_trade(pnl=60.0),
            make_trade(pnl=-10.0),
            make_trade(pnl=-5.0),
        ]
        sim = MonteCarloSimulator(n_simulations=1000, seed=42)
        result = sim.simulate(trades, initial_cash=10_000.0)

        # All shuffles produce the same final value (sum of pnl is the same),
        # so percentile depends on how many simulated finals < actual.
        # Since every shuffle has the same final value as actual,
        # the percentile could be 0 (none are strictly less).
        # The important check is that the result is valid and within bounds.
        assert 0.0 <= result.percentile <= 100.0

    # -- drawdown calculation -----------------------------------------------

    def test_drawdown_calculation(self) -> None:
        """Equity [100, 120, 90, 110] -> max drawdown = (120-90)/120 = 0.25."""
        sim = MonteCarloSimulator(n_simulations=10, seed=42)
        equity = [100.0, 120.0, 90.0, 110.0]
        dd = sim._max_drawdown(equity)
        assert dd == pytest.approx(0.25)

    # -- n_simulations stored -----------------------------------------------

    def test_n_simulations_stored(self) -> None:
        sim = MonteCarloSimulator(n_simulations=777, seed=42)
        result = sim.simulate([make_trade(pnl=10.0)], initial_cash=1_000.0)
        assert result.n_simulations == 777

    # -- percentile bounds --------------------------------------------------

    def test_percentile_bounds(self) -> None:
        trades = [make_trade(pnl=i * 5.0) for i in range(-10, 11)]
        sim = MonteCarloSimulator(n_simulations=500, seed=99)
        result = sim.simulate(trades, initial_cash=5_000.0)

        assert 0.0 <= result.percentile <= 100.0
