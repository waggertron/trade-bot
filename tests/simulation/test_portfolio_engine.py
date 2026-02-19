"""Tests for portfolio-mode engine integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import RiskLevel
from src.data.providers.base import OHLCBar
from src.simulation.engine import SimulationEngine
from src.simulation.models import (
    PortfolioMetrics,
    RiskLevelResult,
    SimulationConfig,
    StockSimResult,
)


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
async def test_portfolio_mode_allocates_capital_per_stock():
    """3 stocks, $30000, portfolio_mode=True -> each stock gets ~$10000."""
    config = SimulationConfig(
        stocks=["AAPL", "GOOG", "MSFT"],
        initial_balance=30000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=20,
        portfolio_mode=True,
    )
    engine = SimulationEngine(config)
    bars = _make_bars(90)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert report.status == "completed"
    result = report.risk_level_results["moderate"]
    assert len(result.stock_results) == 3

    for stock_result in result.stock_results:
        # Each stock should get 1/3 of $30000 = $10000, not the full $30000
        assert stock_result.initial_balance == pytest.approx(10000.0, rel=0.01), (
            f"{stock_result.symbol} got {stock_result.initial_balance}, expected ~10000"
        )


@pytest.mark.asyncio
async def test_portfolio_mode_produces_portfolio_metrics():
    """portfolio_mode=True -> result.portfolio_metrics is not None, has equity_curve."""
    config = SimulationConfig(
        stocks=["AAPL", "GOOG"],
        initial_balance=20000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=20,
        portfolio_mode=True,
    )
    engine = SimulationEngine(config)
    bars = _make_bars(90)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert report.status == "completed"
    result = report.risk_level_results["moderate"]

    # Portfolio metrics should be populated
    assert result.portfolio_metrics is not None
    assert result.portfolio_metrics.initial_balance == pytest.approx(20000.0)
    assert len(result.portfolio_metrics.equity_curve) > 0
    assert result.portfolio_metrics.total_trades >= 0


@pytest.mark.asyncio
async def test_non_portfolio_mode_unchanged():
    """portfolio_mode=False (default) -> portfolio_metrics is None, full balance used."""
    config = SimulationConfig(
        stocks=["AAPL", "GOOG"],
        initial_balance=20000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=20,
        # portfolio_mode defaults to False
    )
    engine = SimulationEngine(config)
    bars = _make_bars(90)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert report.status == "completed"
    result = report.risk_level_results["moderate"]

    # Portfolio metrics should NOT be populated
    assert result.portfolio_metrics is None

    # Each stock should use the FULL initial balance
    for stock_result in result.stock_results:
        assert stock_result.initial_balance == pytest.approx(20000.0), (
            f"{stock_result.symbol} got {stock_result.initial_balance}, expected 20000"
        )


def test_portfolio_recommendation_uses_portfolio_metrics():
    """When portfolio_metrics exists, scoring should use portfolio-level values.

    We construct two risk levels where the per-stock averages favor "conservative"
    but the portfolio-level metrics favor "aggressive". If the recommendation
    picks "aggressive", it means portfolio metrics are being used.
    """
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        portfolio_mode=True,
    )
    engine = SimulationEngine(config)

    # Conservative: good per-stock averages, bad portfolio metrics
    conservative_result = RiskLevelResult(
        risk_level="conservative",
        stock_results=[
            StockSimResult(
                symbol="AAPL",
                initial_balance=10000.0,
                final_value=12000.0,
                total_pnl=2000.0,
                return_pct=20.0,       # high per-stock return
                max_drawdown=5.0,      # low per-stock drawdown
                sharpe_ratio=2.0,      # high per-stock sharpe
                total_trades=10,
                winning_trades=7,
                losing_trades=3,
                win_rate=0.7,
            ),
        ],
        total_return_pct=20.0,         # avg return (from per-stock)
        avg_sharpe=2.0,                # avg sharpe (from per-stock)
        avg_max_drawdown=5.0,          # avg drawdown (from per-stock)
        total_trades=10,
        portfolio_metrics=PortfolioMetrics(
            initial_balance=10000.0,
            final_value=9000.0,
            total_return_pct=-10.0,    # BAD portfolio return
            max_drawdown=15.0,         # BAD portfolio drawdown
            sharpe_ratio=-0.5,         # BAD portfolio sharpe
            sortino_ratio=-0.3,
            calmar_ratio=-0.2,
            total_trades=10,
        ),
    )

    # Aggressive: bad per-stock averages, good portfolio metrics
    aggressive_result = RiskLevelResult(
        risk_level="aggressive",
        stock_results=[
            StockSimResult(
                symbol="AAPL",
                initial_balance=10000.0,
                final_value=10100.0,
                total_pnl=100.0,
                return_pct=1.0,        # low per-stock return
                max_drawdown=10.0,     # high per-stock drawdown
                sharpe_ratio=0.1,      # low per-stock sharpe
                total_trades=10,
                winning_trades=5,
                losing_trades=5,
                win_rate=0.5,
            ),
        ],
        total_return_pct=1.0,          # avg return (from per-stock)
        avg_sharpe=0.1,                # avg sharpe (from per-stock)
        avg_max_drawdown=10.0,         # avg drawdown (from per-stock)
        total_trades=10,
        portfolio_metrics=PortfolioMetrics(
            initial_balance=10000.0,
            final_value=13000.0,
            total_return_pct=30.0,     # GOOD portfolio return
            max_drawdown=3.0,          # GOOD portfolio drawdown
            sharpe_ratio=3.0,          # GOOD portfolio sharpe
            sortino_ratio=4.0,
            calmar_ratio=5.0,
            total_trades=10,
        ),
    )

    results = {
        "conservative": conservative_result,
        "aggressive": aggressive_result,
    }

    recommendation = engine._generate_recommendation(results)

    # If portfolio metrics are used, aggressive should win (sharpe=3.0, return=30%)
    # If per-stock averages are used, conservative should win (sharpe=2.0, return=20%)
    assert recommendation.optimal_risk_level == "aggressive", (
        f"Expected 'aggressive' (portfolio metrics), got '{recommendation.optimal_risk_level}'"
    )


@pytest.mark.asyncio
async def test_portfolio_mc_uses_allocated_balance():
    """In portfolio mode, MC projections should use allocated balance per stock.

    With 3 stocks and $30000, each stock gets $10000. The MC projections' median_final
    should be proportional to $10000, not $30000.
    """
    config = SimulationConfig(
        stocks=["AAPL", "GOOG", "MSFT"],
        initial_balance=30000.0,
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

    # Also run without portfolio mode to compare MC results
    config_non_portfolio = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=50,
        portfolio_mode=False,
    )
    engine_non_portfolio = SimulationEngine(config_non_portfolio)
    with patch.object(engine_non_portfolio, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report_ref = await engine_non_portfolio.run()

    ref_result = report_ref.risk_level_results["moderate"]

    # Both should have MC projections
    assert len(result.monte_carlo_projections) == 3
    assert len(ref_result.monte_carlo_projections) == 1

    # The portfolio-mode MC projection's median_final should match a $10000 run,
    # since each stock gets 1/3 of $30000 = $10000.
    # Compare the first stock's MC projection with the reference $10000 run.
    portfolio_mc = result.monte_carlo_projections[0]
    ref_mc = ref_result.monte_carlo_projections[0]

    # Both use the same seed (42) and same bars, so with $10000 initial balance
    # they should produce the same median_final
    assert portfolio_mc.median_final == pytest.approx(ref_mc.median_final, rel=0.01), (
        f"Portfolio MC median_final={portfolio_mc.median_final} "
        f"should match reference $10k MC median_final={ref_mc.median_final}"
    )
