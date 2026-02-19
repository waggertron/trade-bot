"""Tests for the simulation engine."""
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


@pytest.mark.asyncio
async def test_engine_runs_single_stock():
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=50,
    )
    engine = SimulationEngine(config)
    bars = _make_bars(90)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert report.status == "completed"
    assert "moderate" in report.risk_level_results
    result = report.risk_level_results["moderate"]
    assert len(result.stock_results) == 1
    assert result.stock_results[0].symbol == "AAPL"
    assert len(result.monte_carlo_projections) == 1


@pytest.mark.asyncio
async def test_engine_handles_insufficient_data():
    config = SimulationConfig(
        stocks=["AAPL"],
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.CONSERVATIVE],
        mc_simulations=10,
    )
    engine = SimulationEngine(config)
    bars = _make_bars(10)  # only 10 bars, need 90

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    # Should still complete but with adaptive split
    assert report.status == "completed"


@pytest.mark.asyncio
async def test_engine_multiple_risk_levels():
    config = SimulationConfig(
        stocks=["AAPL"],
        train_days=30,
        test_days=15,
        risk_levels=[RiskLevel.CONSERVATIVE, RiskLevel.AGGRESSIVE],
        mc_simulations=20,
    )
    engine = SimulationEngine(config)
    bars = _make_bars(45)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert "conservative" in report.risk_level_results
    assert "aggressive" in report.risk_level_results


@pytest.mark.asyncio
async def test_engine_generates_recommendation():
    config = SimulationConfig(
        stocks=["AAPL"],
        train_days=30,
        test_days=15,
        risk_levels=[RiskLevel.CONSERVATIVE, RiskLevel.MODERATE],
        mc_simulations=20,
    )
    engine = SimulationEngine(config)
    bars = _make_bars(45)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert report.recommendation is not None
    assert report.recommendation.optimal_risk_level in ("conservative", "moderate")
    assert report.recommendation.reasoning != ""
