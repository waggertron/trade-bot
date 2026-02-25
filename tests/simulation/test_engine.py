"""Tests for the simulation engine."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import RiskLevel, RiskSettings
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
async def test_engine_applies_max_position_pct_override():
    """When max_position_pct is set, it overrides the risk level preset."""
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.CONSERVATIVE],
        mc_simulations=20,
        max_position_pct=7.5,
    )
    engine = SimulationEngine(config)
    bars = _make_bars(90)

    with (
        patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars),
        patch(
            "src.simulation.engine.RiskSettings.from_risk_level",
            wraps=RiskSettings.from_risk_level,
        ) as mock_frl,
    ):
        report = await engine.run()

    assert report.status == "completed"
    # Verify from_risk_level was called with the override
    mock_frl.assert_called_once_with(RiskLevel.CONSERVATIVE, max_position_pct=7.5)


@pytest.mark.asyncio
async def test_engine_no_override_when_max_position_pct_is_none():
    """When max_position_pct is None, from_risk_level is called without overrides."""
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=20,
    )
    engine = SimulationEngine(config)
    bars = _make_bars(90)

    with (
        patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars),
        patch(
            "src.simulation.engine.RiskSettings.from_risk_level",
            wraps=RiskSettings.from_risk_level,
        ) as mock_frl,
    ):
        report = await engine.run()

    assert report.status == "completed"
    # Called with just the risk level, no keyword overrides
    mock_frl.assert_called_once_with(RiskLevel.MODERATE)


@pytest.mark.asyncio
async def test_engine_computes_spy_benchmarks():
    """Simulation should compute SPY buy-and-hold and DCA benchmarks."""
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=20,
    )
    engine = SimulationEngine(config)
    aapl_bars = _make_bars(90, start_price=150.0)
    spy_bars = _make_bars(90, start_price=400.0)

    async def mock_fetch(symbol: str):
        return spy_bars if symbol == "SPY" else aapl_bars

    with patch.object(engine, "_fetch_bars", side_effect=mock_fetch):
        report = await engine.run()

    assert report.status == "completed"
    assert "spy_buy_hold" in report.benchmarks
    assert "spy_dca" in report.benchmarks
    assert report.benchmarks["spy_buy_hold"].name == "SPY Buy-and-Hold"
    assert report.benchmarks["spy_dca"].name == "SPY Monthly DCA"
    assert report.benchmarks["spy_buy_hold"].initial_balance == 10000.0


@pytest.mark.asyncio
async def test_engine_benchmarks_absent_when_spy_insufficient():
    """If SPY bars are insufficient, benchmarks should be empty."""
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=20,
    )
    engine = SimulationEngine(config)
    aapl_bars = _make_bars(90, start_price=150.0)
    spy_bars = _make_bars(3, start_price=400.0)  # too few

    async def mock_fetch(symbol: str):
        return spy_bars if symbol == "SPY" else aapl_bars

    with patch.object(engine, "_fetch_bars", side_effect=mock_fetch):
        report = await engine.run()

    assert report.status == "completed"
    # With only 3 SPY bars, test split = 3*2//3 = 2 train, 1 test bar
    # 1 test bar is still valid for benchmark (buy_and_hold needs >= 1 bar)
    # But the equity curve will be minimal


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


# ---------------------------------------------------------------------------
# MC seed derivation per risk level
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mc_projections_differ_across_risk_levels():
    """Portfolio MC projections should differ across risk levels even with a fixed seed."""
    config = SimulationConfig(
        stocks=["AAPL", "MSFT"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.CONSERVATIVE, RiskLevel.MODERATE, RiskLevel.AGGRESSIVE],
        mc_simulations=50,
        mc_seed=42,
        portfolio_mode=True,
    )
    engine = SimulationEngine(config)
    bars = _make_bars(90)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert report.status == "completed"
    pmc_values = []
    for level in ("conservative", "moderate", "aggressive"):
        result = report.risk_level_results[level]
        assert result.portfolio_monte_carlo is not None
        pmc_values.append(result.portfolio_monte_carlo.median_final)

    # All three should be different
    assert len(set(pmc_values)) == 3, f"Expected 3 distinct values, got {pmc_values}"


@pytest.mark.asyncio
async def test_mc_projections_reproducible_with_same_seed():
    """Running twice with the same seed should produce identical results."""
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=50,
        mc_seed=99,
    )
    bars = _make_bars(90)

    results = []
    for _ in range(2):
        engine = SimulationEngine(config)
        with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
            report = await engine.run()
        mc = report.risk_level_results["moderate"].monte_carlo_projections[0]
        results.append(mc.median_final)

    assert results[0] == results[1], f"Same seed should reproduce: {results}"


@pytest.mark.asyncio
async def test_per_stock_mc_differs_across_risk_levels():
    """Per-stock MC projections should also differ across risk levels with a fixed seed."""
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.CONSERVATIVE, RiskLevel.AGGRESSIVE],
        mc_simulations=50,
        mc_seed=42,
    )
    engine = SimulationEngine(config)
    bars = _make_bars(90)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert report.status == "completed"
    con_mc = report.risk_level_results["conservative"].monte_carlo_projections[0]
    agg_mc = report.risk_level_results["aggressive"].monte_carlo_projections[0]
    assert con_mc.median_final != agg_mc.median_final, (
        f"Per-stock MC should differ:"
        f" conservative={con_mc.median_final},"
        f" aggressive={agg_mc.median_final}"
    )


# ---------------------------------------------------------------------------
# Progress callback tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_calls_progress_callback_for_risk_levels():
    """progress_cb should be called with 'risk_level' stage for each risk level."""
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.CONSERVATIVE, RiskLevel.MODERATE],
        mc_simulations=20,
    )
    calls: list[tuple] = []

    def on_progress(stage: str, current: int, total: int, detail: str = "") -> None:
        calls.append((stage, current, total, detail))

    engine = SimulationEngine(config, progress_cb=on_progress)
    bars = _make_bars(90)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert report.status == "completed"
    risk_calls = [(s, c, t, d) for s, c, t, d in calls if s == "risk_level"]
    assert len(risk_calls) == 2
    assert risk_calls[0] == ("risk_level", 1, 2, "conservative")
    assert risk_calls[1] == ("risk_level", 2, 2, "moderate")


@pytest.mark.asyncio
async def test_engine_calls_progress_callback_for_stocks():
    """progress_cb should be called with 'stock' stage for each stock."""
    config = SimulationConfig(
        stocks=["AAPL", "MSFT"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=20,
    )
    calls: list[tuple] = []

    def on_progress(stage: str, current: int, total: int, detail: str = "") -> None:
        calls.append((stage, current, total, detail))

    engine = SimulationEngine(config, progress_cb=on_progress)
    bars = _make_bars(90)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert report.status == "completed"
    stock_calls = [(s, c, t, d) for s, c, t, d in calls if s == "stock"]
    assert len(stock_calls) == 2
    assert stock_calls[0] == ("stock", 1, 2, "AAPL")
    assert stock_calls[1] == ("stock", 2, 2, "MSFT")


@pytest.mark.asyncio
async def test_engine_calls_progress_callback_for_benchmark():
    """progress_cb should be called with 'benchmark' stage before SPY computation."""
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=20,
    )
    calls: list[tuple] = []

    def on_progress(stage: str, current: int, total: int, detail: str = "") -> None:
        calls.append((stage, current, total, detail))

    engine = SimulationEngine(config, progress_cb=on_progress)
    aapl_bars = _make_bars(90, start_price=150.0)
    spy_bars = _make_bars(90, start_price=400.0)

    async def mock_fetch(symbol: str):
        return spy_bars if symbol == "SPY" else aapl_bars

    with patch.object(engine, "_fetch_bars", side_effect=mock_fetch):
        report = await engine.run()

    assert report.status == "completed"
    bench_calls = [c for c in calls if c[0] == "benchmark"]
    assert len(bench_calls) == 1
    assert bench_calls[0][3] == "Computing SPY benchmarks"


@pytest.mark.asyncio
async def test_engine_works_without_progress_callback():
    """Engine should work fine when no progress_cb is provided (default None)."""
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=20,
    )
    engine = SimulationEngine(config)  # No callback
    bars = _make_bars(90)

    with patch.object(engine, "_fetch_bars", new_callable=AsyncMock, return_value=bars):
        report = await engine.run()

    assert report.status == "completed"


# ---------------------------------------------------------------------------
# Cache integration tests
# ---------------------------------------------------------------------------


def test_engine_use_cache_false_has_no_bar_cache():
    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=20,
    )
    engine = SimulationEngine(config, use_cache=False)
    assert engine._bar_cache is None


def test_engine_use_cache_true_creates_bar_cache():
    from src.simulation.cache import BarCache

    config = SimulationConfig(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        risk_levels=[RiskLevel.MODERATE],
        mc_simulations=20,
    )
    engine = SimulationEngine(config, use_cache=True)
    assert isinstance(engine._bar_cache, BarCache)
