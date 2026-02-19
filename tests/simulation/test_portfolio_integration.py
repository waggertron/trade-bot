"""Integration tests for the portfolio simulation system.

These tests exercise the full pipeline: engine -> backtest -> MC projection -> portfolio metrics,
verifying end-to-end behavior for portfolio mode, backward compatibility, custom weights,
single-stock portfolios, and serialization round-trips.
"""
from __future__ import annotations

import json
import random
from unittest.mock import patch

import pytest

from src.core.config import RiskLevel
from src.data.providers.base import OHLCBar
from src.simulation.engine import SimulationEngine
from src.simulation.models import (
    AllocationWeights,
    RebalanceConfig,
    SimulationConfig,
)


def _make_bars(
    n: int, start_price: float = 150.0, volatility: float = 2.0,
) -> list[OHLCBar]:
    """Create n daily bars simulating realistic stock price movement."""
    random.seed(42)
    bars: list[OHLCBar] = []
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


def _make_bars_for_symbol(
    symbol: str, n: int = 90, base_price: float = 100.0,
) -> list[OHLCBar]:
    """Create n daily bars with a seed derived from the symbol name."""
    seed = hash(symbol) % 1000
    random.seed(seed)
    start_price = base_price + hash(symbol) % 200
    bars: list[OHLCBar] = []
    base_ts = 1700000000
    price = start_price
    for i in range(n):
        change = random.gauss(0.1, 2.0)
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


# --------------------------------------------------------------------------- #
# 1. Full portfolio pipeline
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_full_portfolio_pipeline():
    """3 stocks, 2 risk levels, portfolio_mode=True, weekly rebalancing.

    Verifies:
    - report completes successfully
    - both risk levels present
    - portfolio metrics and MC populated for each risk level
    - correlation matrix has correct dimensions (3x3)
    - recommendation selects one of the risk levels
    """
    config = SimulationConfig(
        stocks=["AAPL", "MSFT", "GOOGL"],
        initial_balance=10_000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.CONSERVATIVE, RiskLevel.MODERATE],
        mc_simulations=50,
        portfolio_mode=True,
        rebalance=RebalanceConfig(frequency="weekly"),
    )
    engine = SimulationEngine(config)

    async def mock_fetch(symbol: str) -> list[OHLCBar]:
        return _make_bars_for_symbol(symbol, n=90)

    with patch.object(engine, "_fetch_bars", side_effect=mock_fetch):
        report = await engine.run()

    # Top-level checks
    assert report.status == "completed"
    assert "conservative" in report.risk_level_results
    assert "moderate" in report.risk_level_results

    for level_name in ["conservative", "moderate"]:
        result = report.risk_level_results[level_name]

        # Portfolio metrics
        assert result.portfolio_metrics is not None, (
            f"{level_name}: portfolio_metrics should not be None"
        )
        assert len(result.portfolio_metrics.equity_curve) > 0, (
            f"{level_name}: equity_curve should have entries"
        )
        assert result.portfolio_metrics.initial_balance == config.initial_balance
        assert result.portfolio_metrics.total_trades >= 0

        # Portfolio Monte Carlo
        assert result.portfolio_monte_carlo is not None, (
            f"{level_name}: portfolio_monte_carlo should not be None"
        )
        corr = result.portfolio_monte_carlo.correlation_matrix
        assert len(corr) == 3, f"correlation_matrix rows: expected 3, got {len(corr)}"
        for row in corr:
            assert len(row) == 3, f"correlation_matrix cols: expected 3, got {len(row)}"
        assert result.portfolio_monte_carlo.n_paths == config.mc_simulations

    # Recommendation
    assert report.recommendation is not None
    assert report.recommendation.optimal_risk_level in ("conservative", "moderate")


# --------------------------------------------------------------------------- #
# 2. Backward compatibility (portfolio_mode=False)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_backward_compatibility():
    """portfolio_mode=False -> no portfolio metrics/MC; each stock uses full balance."""
    config = SimulationConfig(
        stocks=["AAPL", "MSFT"],
        initial_balance=10_000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.CONSERVATIVE, RiskLevel.MODERATE],
        mc_simulations=50,
        # portfolio_mode defaults to False
    )
    engine = SimulationEngine(config)

    async def mock_fetch(symbol: str) -> list[OHLCBar]:
        return _make_bars_for_symbol(symbol, n=90)

    with patch.object(engine, "_fetch_bars", side_effect=mock_fetch):
        report = await engine.run()

    assert report.status == "completed"

    for level_name in ["conservative", "moderate"]:
        result = report.risk_level_results[level_name]

        # Portfolio-level fields should be absent
        assert result.portfolio_metrics is None, (
            f"{level_name}: portfolio_metrics should be None in non-portfolio mode"
        )
        assert result.portfolio_monte_carlo is None, (
            f"{level_name}: portfolio_monte_carlo should be None in non-portfolio mode"
        )

        # Each stock should use the FULL initial balance (no splitting)
        for sr in result.stock_results:
            assert sr.initial_balance == pytest.approx(config.initial_balance), (
                f"{sr.symbol} in {level_name}: expected full balance "
                f"{config.initial_balance}, got {sr.initial_balance}"
            )


# --------------------------------------------------------------------------- #
# 3. Custom weights
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_custom_weights():
    """portfolio_mode=True with custom weights (70/30) and $20000 balance.

    Verifies capital allocation respects custom weights.
    """
    config = SimulationConfig(
        stocks=["AAPL", "MSFT"],
        initial_balance=20_000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=50,
        portfolio_mode=True,
        allocation=AllocationWeights(
            mode="custom",
            weights={"AAPL": 0.7, "MSFT": 0.3},
        ),
    )
    engine = SimulationEngine(config)

    async def mock_fetch(symbol: str) -> list[OHLCBar]:
        return _make_bars_for_symbol(symbol, n=90)

    with patch.object(engine, "_fetch_bars", side_effect=mock_fetch):
        report = await engine.run()

    assert report.status == "completed"
    result = report.risk_level_results["moderate"]

    # Find stock results by symbol
    by_symbol = {sr.symbol: sr for sr in result.stock_results}
    assert "AAPL" in by_symbol
    assert "MSFT" in by_symbol

    # AAPL should get 70% of $20000 = $14000
    assert by_symbol["AAPL"].initial_balance == pytest.approx(14_000.0, rel=0.01), (
        f"AAPL balance: expected ~14000, got {by_symbol['AAPL'].initial_balance}"
    )

    # MSFT should get 30% of $20000 = $6000
    assert by_symbol["MSFT"].initial_balance == pytest.approx(6_000.0, rel=0.01), (
        f"MSFT balance: expected ~6000, got {by_symbol['MSFT'].initial_balance}"
    )

    # Portfolio metrics should exist
    assert result.portfolio_metrics is not None


# --------------------------------------------------------------------------- #
# 4. Single stock in portfolio mode
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_single_stock_portfolio_mode():
    """portfolio_mode=True with only 1 stock should still work.

    Verifies:
    - portfolio metrics exist with equity curve
    - MC correlation matrix is 1x1 ([[1.0]])
    """
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10_000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=50,
        portfolio_mode=True,
    )
    engine = SimulationEngine(config)

    async def mock_fetch(symbol: str) -> list[OHLCBar]:
        return _make_bars_for_symbol(symbol, n=90)

    with patch.object(engine, "_fetch_bars", side_effect=mock_fetch):
        report = await engine.run()

    assert report.status == "completed"
    result = report.risk_level_results["moderate"]

    # Portfolio metrics should exist
    assert result.portfolio_metrics is not None
    assert len(result.portfolio_metrics.equity_curve) > 0

    # Portfolio MC should exist with 1x1 correlation matrix
    assert result.portfolio_monte_carlo is not None
    corr = result.portfolio_monte_carlo.correlation_matrix
    assert len(corr) == 1, f"Expected 1x1 correlation matrix, got {len(corr)} rows"
    assert len(corr[0]) == 1
    assert corr[0][0] == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# 5. Serialization round-trip
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_portfolio_serialization_roundtrip():
    """Run portfolio simulation, serialize with model_dump(), verify JSON-serializable.

    Checks:
    - model_dump() returns a dict
    - portfolio_metrics and portfolio_monte_carlo keys present
    - All values are JSON-serializable (json.dumps succeeds)
    """
    config = SimulationConfig(
        stocks=["AAPL", "MSFT"],
        initial_balance=10_000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=50,
        portfolio_mode=True,
    )
    engine = SimulationEngine(config)

    async def mock_fetch(symbol: str) -> list[OHLCBar]:
        return _make_bars_for_symbol(symbol, n=90)

    with patch.object(engine, "_fetch_bars", side_effect=mock_fetch):
        report = await engine.run()

    assert report.status == "completed"

    # Serialize
    report_dict = report.model_dump()

    assert isinstance(report_dict, dict)

    # Check portfolio fields exist in the risk level result
    moderate_dict = report_dict["risk_level_results"]["moderate"]
    assert "portfolio_metrics" in moderate_dict
    assert "portfolio_monte_carlo" in moderate_dict
    assert moderate_dict["portfolio_metrics"] is not None
    assert moderate_dict["portfolio_monte_carlo"] is not None

    # Verify everything is JSON-serializable (no numpy arrays, etc.)
    serialized = json.dumps(report_dict)
    assert isinstance(serialized, str)
    assert len(serialized) > 0

    # Round-trip: deserialize and check key fields survive
    deserialized = json.loads(serialized)
    assert deserialized["status"] == "completed"
    assert deserialized["risk_level_results"]["moderate"]["portfolio_metrics"]["initial_balance"] == config.initial_balance
