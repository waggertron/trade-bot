"""Tests that mc_seed produces deterministic Monte Carlo projections at the engine level."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import RiskLevel
from src.data.providers.base import OHLCBar
from src.simulation.engine import SimulationEngine
from src.simulation.models import SimulationConfig


def _make_bars(n: int, start_price: float = 100.0) -> list[OHLCBar]:
    """Create n daily bars with a slight upward trend."""
    bars = []
    base_ts = 1700000000
    for i in range(n):
        price = start_price + i * 0.5
        bars.append(
            OHLCBar(
                timestamp=base_ts + i * 86400,
                open=str(price - 0.2),
                high=str(price + 1.0),
                low=str(price - 1.0),
                close=str(price),
                volume=str(1000000),
                source="yfinance",
            )
        )
    return bars


@pytest.mark.asyncio
async def test_same_mc_seed_produces_identical_projections():
    """Running the engine twice with the same mc_seed yields identical MC results."""
    seed = 12345
    config = SimulationConfig(
        stocks=["AAPL", "MSFT"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=100,
        mc_seed=seed,
    )
    bars = _make_bars(90)

    # First run
    engine1 = SimulationEngine(config)
    with patch.object(engine1, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report1 = await engine1.run()

    # Second run (fresh engine, same config)
    engine2 = SimulationEngine(config)
    with patch.object(engine2, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report2 = await engine2.run()

    assert report1.status == "completed"
    assert report2.status == "completed"

    result1 = report1.risk_level_results["moderate"]
    result2 = report2.risk_level_results["moderate"]

    # Both should have MC projections for both stocks
    assert len(result1.monte_carlo_projections) == 2
    assert len(result2.monte_carlo_projections) == 2

    # Compare MC projections: same seed -> identical results
    for mc1, mc2 in zip(
        result1.monte_carlo_projections, result2.monte_carlo_projections, strict=False
    ):
        assert mc1.symbol == mc2.symbol
        assert mc1.median_final == pytest.approx(mc2.median_final), (
            f"{mc1.symbol}: median_final {mc1.median_final} != {mc2.median_final}"
        )
        assert mc1.p5_final == pytest.approx(mc2.p5_final), (
            f"{mc1.symbol}: p5_final {mc1.p5_final} != {mc2.p5_final}"
        )
        assert mc1.p95_final == pytest.approx(mc2.p95_final), (
            f"{mc1.symbol}: p95_final {mc1.p95_final} != {mc2.p95_final}"
        )
        assert mc1.worst_drawdown_p95 == pytest.approx(mc2.worst_drawdown_p95), (
            f"{mc1.symbol}: worst_drawdown_p95 {mc1.worst_drawdown_p95} != {mc2.worst_drawdown_p95}"
        )


@pytest.mark.asyncio
async def test_different_mc_seed_produces_different_projections():
    """Running the engine with two different mc_seeds yields different MC results."""
    base_kwargs = dict(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=100,
    )
    config_a = SimulationConfig(**base_kwargs, mc_seed=111)
    config_b = SimulationConfig(**base_kwargs, mc_seed=999)
    bars = _make_bars(90)

    engine_a = SimulationEngine(config_a)
    with patch.object(engine_a, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report_a = await engine_a.run()

    engine_b = SimulationEngine(config_b)
    with patch.object(engine_b, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report_b = await engine_b.run()

    assert report_a.status == "completed"
    assert report_b.status == "completed"

    mc_a = report_a.risk_level_results["moderate"].monte_carlo_projections[0]
    mc_b = report_b.risk_level_results["moderate"].monte_carlo_projections[0]

    # With different seeds, at least one MC statistic should differ
    differs = (
        mc_a.median_final != pytest.approx(mc_b.median_final, rel=1e-6)
        or mc_a.p5_final != pytest.approx(mc_b.p5_final, rel=1e-6)
        or mc_a.p95_final != pytest.approx(mc_b.p95_final, rel=1e-6)
    )
    assert differs, (
        f"Expected different MC results with different seeds, "
        f"but got identical: median_final={mc_a.median_final}"
    )
