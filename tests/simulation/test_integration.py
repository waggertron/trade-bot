"""Integration test: full simulation pipeline end-to-end."""
from __future__ import annotations

import random
from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import RiskLevel
from src.data.providers.base import OHLCBar
from src.simulation.engine import SimulationEngine
from src.simulation.models import SimulationConfig


def _make_bars(n: int, start_price: float = 150.0, volatility: float = 2.0) -> list[OHLCBar]:
    """Create n daily bars simulating realistic stock price movement."""
    random.seed(42)
    bars = []
    base_ts = 1700000000
    price = start_price
    for i in range(n):
        change = random.gauss(0.1, volatility)
        price = max(1.0, price + change)
        bars.append(OHLCBar(
            timestamp=base_ts + i * 86400,
            open=f"{price - 0.5:.2f}",
            high=f"{price + abs(change):.2f}",
            low=f"{price - abs(change):.2f}",
            close=f"{price:.2f}",
            volume=str(random.randint(500000, 5000000)),
            source="yfinance",
        ))
    return bars


@pytest.mark.asyncio
async def test_full_simulation_pipeline():
    """Run a complete simulation with 2 stocks, 2 risk levels, verify all outputs."""
    config = SimulationConfig(
        stocks=["AAPL", "MSFT"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.CONSERVATIVE, RiskLevel.MODERATE],
        mc_simulations=50,
    )
    engine = SimulationEngine(config)
    bars_aapl = _make_bars(90, start_price=180.0)
    bars_msft = _make_bars(90, start_price=400.0)

    async def mock_fetch(symbol):
        return bars_aapl if symbol == "AAPL" else bars_msft

    with patch.object(engine, "_fetch_bars", side_effect=mock_fetch):
        report = await engine.run()

    # Verify report structure
    assert report.status == "completed"
    assert report.id != ""
    assert report.started_at != ""
    assert report.completed_at != ""
    assert report.error is None

    # Verify both risk levels present
    assert "conservative" in report.risk_level_results
    assert "moderate" in report.risk_level_results

    for level_name in ["conservative", "moderate"]:
        result = report.risk_level_results[level_name]
        assert result.risk_level == level_name

        # Should have results for both stocks
        assert len(result.stock_results) == 2
        symbols = {sr.symbol for sr in result.stock_results}
        assert symbols == {"AAPL", "MSFT"}

        # Each stock should have MC projection
        assert len(result.monte_carlo_projections) == 2

        # Verify stock result fields
        for sr in result.stock_results:
            assert sr.initial_balance == 10000.0
            assert sr.final_value > 0
            assert isinstance(sr.equity_curve, list)

        # Verify MC projection fields
        for mc in result.monte_carlo_projections:
            assert mc.n_paths == 50
            assert mc.p5_final < mc.p95_final

    # Verify recommendation
    assert report.recommendation is not None
    assert report.recommendation.optimal_risk_level in ("conservative", "moderate")
    assert report.recommendation.reasoning != ""
    assert 0.0 <= report.recommendation.confidence <= 1.0

    # Verify serialization works
    report_dict = report.model_dump()
    assert isinstance(report_dict, dict)
    assert "risk_level_results" in report_dict
