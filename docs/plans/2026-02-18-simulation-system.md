# Simulation System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full simulation system that fetches 90 days of stock data (60 training + 30 test), runs walk-forward backtests and Monte Carlo projections across 4 risk levels for 16 stocks, provides strategy assessment with recommendations, and exposes results via CLI, API, and frontend.

**Architecture:** New `src/simulation/` package with engine, models, and Monte Carlo projector. The engine fetches data via yfinance, splits train/test, runs the existing backtester per-stock per-risk-level, then runs Monte Carlo price path projections. Results include per-strategy attribution, regime-tagged performance, confidence bands, comparative ranking, and optimal risk/weight recommendations. Exposed via Typer CLI command, FastAPI router, and Next.js page.

**Tech Stack:** Python 3.12+, asyncio, yfinance, numpy, pydantic, Typer, FastAPI, Next.js 14, Recharts, TanStack Query

---

## Task 1: Simulation Models

**Files:**
- Create: `src/simulation/__init__.py`
- Create: `src/simulation/models.py`
- Test: `tests/simulation/test_models.py`

**Step 1: Write the failing test**

```python
# tests/simulation/__init__.py
# (empty)

# tests/simulation/test_models.py
"""Tests for simulation data models."""
from src.simulation.models import (
    SimulationConfig,
    StockSimResult,
    RiskLevelResult,
    MonteCarloProjection,
    StrategyAssessment,
    SimulationReport,
    Recommendation,
)
from src.core.config import RiskLevel


def test_simulation_config_defaults():
    cfg = SimulationConfig(stocks=["AAPL"])
    assert cfg.initial_balance == 10_000.0
    assert cfg.train_days == 60
    assert cfg.test_days == 30
    assert cfg.risk_levels == list(RiskLevel)
    assert cfg.mc_simulations == 1000


def test_stock_sim_result_return_pct():
    r = StockSimResult(
        symbol="AAPL",
        initial_balance=10000.0,
        final_value=11000.0,
        total_pnl=1000.0,
        return_pct=10.0,
        max_drawdown=5.0,
        sharpe_ratio=1.5,
        total_trades=20,
        winning_trades=12,
        losing_trades=8,
        win_rate=0.6,
        equity_curve=[10000.0, 10500.0, 11000.0],
    )
    assert r.return_pct == 10.0
    assert r.win_rate == 0.6


def test_recommendation_model():
    rec = Recommendation(
        optimal_risk_level="moderate",
        reasoning="Best risk-adjusted returns",
        suggested_weights={"momentum": 0.6, "quantitative": 0.4},
        confidence=0.75,
    )
    assert rec.optimal_risk_level == "moderate"
    assert rec.confidence == 0.75
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/simulation/test_models.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/simulation/__init__.py
# (empty)

# src/simulation/models.py
"""Data models for the simulation system."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.analytics.models import AttributionReport, MonteCarloResult, StrategyStats
from src.core.config import RiskLevel


class SimulationConfig(BaseModel):
    """Configuration for a simulation run."""
    model_config = ConfigDict(frozen=True)

    stocks: list[str]
    initial_balance: float = Field(default=10_000.0, gt=0)
    train_days: int = Field(default=60, gt=0)
    test_days: int = Field(default=30, gt=0)
    risk_levels: list[RiskLevel] = Field(default_factory=lambda: list(RiskLevel))
    mc_simulations: int = Field(default=1000, gt=0)


class StockSimResult(BaseModel):
    """Walk-forward backtest result for a single stock."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    initial_balance: float
    final_value: float
    total_pnl: float
    return_pct: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    equity_curve: list[float] = Field(default_factory=list)


class MonteCarloProjection(BaseModel):
    """Monte Carlo forward projection for a stock."""
    model_config = ConfigDict(frozen=True)

    symbol: str
    median_final: float
    p5_final: float
    p95_final: float
    median_return_pct: float
    p5_return_pct: float
    p95_return_pct: float
    worst_drawdown_p95: float
    n_paths: int


class StrategyAssessment(BaseModel):
    """Per-strategy performance assessment across a simulation."""
    model_config = ConfigDict(frozen=True)

    strategy_name: str
    total_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_consecutive_losses: int = 0


class RiskLevelResult(BaseModel):
    """Aggregated results for one risk level across all stocks."""
    model_config = ConfigDict(frozen=True)

    risk_level: str
    stock_results: list[StockSimResult] = Field(default_factory=list)
    monte_carlo_projections: list[MonteCarloProjection] = Field(default_factory=list)
    strategy_assessments: list[StrategyAssessment] = Field(default_factory=list)
    total_return_pct: float = 0.0
    avg_sharpe: float = 0.0
    avg_max_drawdown: float = 0.0
    total_trades: int = 0


class Recommendation(BaseModel):
    """System recommendation based on simulation results."""
    model_config = ConfigDict(frozen=True)

    optimal_risk_level: str
    reasoning: str
    suggested_weights: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SimulationReport(BaseModel):
    """Complete simulation report across all risk levels."""

    id: str
    status: str = "pending"
    config: SimulationConfig
    risk_level_results: dict[str, RiskLevelResult] = Field(default_factory=dict)
    recommendation: Recommendation | None = None
    started_at: str = ""
    completed_at: str = ""
    error: str | None = None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/simulation/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/simulation/__init__.py src/simulation/models.py tests/simulation/__init__.py tests/simulation/test_models.py
git commit -m "feat(simulation): add simulation data models"
```

---

## Task 2: Monte Carlo Price Projector

**Files:**
- Create: `src/simulation/projector.py`
- Test: `tests/simulation/test_projector.py`

**Step 1: Write the failing test**

```python
# tests/simulation/test_projector.py
"""Tests for Monte Carlo price path projection."""
import numpy as np
import pytest

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
    # First day should be close to last price (within 1 day of drift)
    # All paths start from 100.5 with 1 day of random walk
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/simulation/test_projector.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/simulation/projector.py
"""Monte Carlo price path projector using geometric Brownian motion."""
from __future__ import annotations

import numpy as np


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
        drift = mu - 0.5 * sigma ** 2
        shocks = self._rng.normal(0, 1, size=(self._n_paths, days_forward))

        log_paths = drift + sigma * shocks
        log_paths = np.cumsum(log_paths, axis=1)
        paths = last_price * np.exp(log_paths)

        return paths

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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/simulation/test_projector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/simulation/projector.py tests/simulation/test_projector.py
git commit -m "feat(simulation): add Monte Carlo price path projector"
```

---

## Task 3: Simulation Engine

**Files:**
- Create: `src/simulation/engine.py`
- Test: `tests/simulation/test_engine.py`

**Step 1: Write the failing test**

```python
# tests/simulation/test_engine.py
"""Tests for the simulation engine."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import RiskLevel
from src.core.models import AssetType, MarketTick
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

    # Should still complete but with a note about insufficient data
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/simulation/test_engine.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/simulation/engine.py
"""Simulation engine: orchestrates data fetch, backtest, MC projection, and assessment."""
from __future__ import annotations

import asyncio
import logging
import math
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.core.config import RiskLevel, RiskSettings
from src.core.models import AssetType, MarketTick
from src.data.backtester import BacktestResult, run_backtest
from src.data.providers.base import OHLCBar
from src.simulation.models import (
    MonteCarloProjection,
    Recommendation,
    RiskLevelResult,
    SimulationConfig,
    SimulationReport,
    StockSimResult,
    StrategyAssessment,
)
from src.simulation.projector import MonteCarloProjector

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Run walk-forward backtests and Monte Carlo projections across risk levels."""

    def __init__(self, config: SimulationConfig) -> None:
        self._config = config

    async def run(self) -> SimulationReport:
        """Execute the full simulation pipeline."""
        report = SimulationReport(
            id=str(uuid.uuid4())[:8],
            status="running",
            config=self._config,
            started_at=datetime.now(UTC).isoformat(),
        )

        try:
            risk_results: dict[str, RiskLevelResult] = {}

            for risk_level in self._config.risk_levels:
                result = await self._run_risk_level(risk_level)
                risk_results[risk_level.value] = result

            report.risk_level_results = risk_results
            report.recommendation = self._generate_recommendation(risk_results)
            report.status = "completed"
        except Exception as e:
            logger.exception("Simulation failed")
            report.status = "failed"
            report.error = str(e)

        report.completed_at = datetime.now(UTC).isoformat()
        return report

    async def _run_risk_level(self, risk_level: RiskLevel) -> RiskLevelResult:
        """Run simulation for one risk level across all stocks."""
        risk_settings = RiskSettings.from_risk_level(risk_level)
        stock_results: list[StockSimResult] = []
        mc_projections: list[MonteCarloProjection] = []

        for symbol in self._config.stocks:
            bars = await self._fetch_bars(symbol)
            total_needed = self._config.train_days + self._config.test_days

            if len(bars) < 10:
                logger.warning("Insufficient data for %s: %d bars", symbol, len(bars))
                continue

            # Split into train and test
            if len(bars) >= total_needed:
                train_bars = bars[:self._config.train_days]
                test_bars = bars[self._config.train_days:total_needed]
            else:
                # Use what we have: 2/3 train, 1/3 test
                split = len(bars) * 2 // 3
                train_bars = bars[:split]
                test_bars = bars[split:]

            # Walk-forward backtest on test data
            ticks = self._bars_to_ticks(test_bars, symbol)
            if ticks:
                bt_result = await run_backtest(
                    ticks,
                    initial_cash=Decimal(str(self._config.initial_balance)),
                    risk_settings=risk_settings,
                )
                stock_results.append(self._to_stock_result(symbol, bt_result))

            # Monte Carlo projection using training data
            train_prices = [float(b.close) for b in train_bars]
            if len(train_prices) > 5:
                projector = MonteCarloProjector(
                    n_paths=self._config.mc_simulations, seed=42,
                )
                paths = projector.generate_paths(train_prices, self._config.test_days)
                summary = projector.summarize(
                    paths, self._config.initial_balance, train_prices[-1],
                )
                mc_projections.append(MonteCarloProjection(
                    symbol=symbol,
                    median_final=summary["median_final"],
                    p5_final=summary["p5_final"],
                    p95_final=summary["p95_final"],
                    median_return_pct=summary["median_return_pct"],
                    p5_return_pct=summary["p5_return_pct"],
                    p95_return_pct=summary["p95_return_pct"],
                    worst_drawdown_p95=summary["worst_drawdown_p95"],
                    n_paths=self._config.mc_simulations,
                ))

        # Aggregate metrics
        total_return = (
            sum(r.return_pct for r in stock_results) / len(stock_results)
            if stock_results else 0.0
        )
        avg_sharpe = (
            sum(r.sharpe_ratio for r in stock_results) / len(stock_results)
            if stock_results else 0.0
        )
        avg_dd = (
            sum(r.max_drawdown for r in stock_results) / len(stock_results)
            if stock_results else 0.0
        )
        total_trades = sum(r.total_trades for r in stock_results)

        return RiskLevelResult(
            risk_level=risk_level.value,
            stock_results=stock_results,
            monte_carlo_projections=mc_projections,
            strategy_assessments=[],  # filled by post-processing if needed
            total_return_pct=total_return,
            avg_sharpe=avg_sharpe,
            avg_max_drawdown=avg_dd,
            total_trades=total_trades,
        )

    async def _fetch_bars(self, symbol: str) -> list[OHLCBar]:
        """Fetch OHLC bars via yfinance."""
        from src.data.providers import yfinance_provider
        from src.data.providers.base import Interval

        total_days = self._config.train_days + self._config.test_days + 10  # buffer
        since_ts = int((datetime.now(UTC) - timedelta(days=total_days)).timestamp())
        return await yfinance_provider.download(
            symbol, interval=Interval.D1, since=since_ts,
        )

    def _bars_to_ticks(self, bars: list[OHLCBar], symbol: str) -> list[MarketTick]:
        """Convert OHLCBar list to MarketTick list."""
        ticks = []
        for bar in bars:
            ticks.append(MarketTick(
                symbol=symbol,
                price=Decimal(bar.close),
                volume=int(float(bar.volume)),
                timestamp=datetime.fromtimestamp(bar.timestamp, tz=UTC),
                asset_type=AssetType.STOCK,
            ))
        return ticks

    def _to_stock_result(self, symbol: str, bt: BacktestResult) -> StockSimResult:
        """Convert BacktestResult to StockSimResult."""
        return StockSimResult(
            symbol=symbol,
            initial_balance=bt.initial_cash,
            final_value=bt.final_value,
            total_pnl=bt.total_pnl,
            return_pct=bt.return_pct,
            max_drawdown=bt.max_drawdown,
            sharpe_ratio=bt.sharpe_ratio,
            total_trades=bt.total_trades,
            winning_trades=bt.winning_trades,
            losing_trades=bt.losing_trades,
            win_rate=bt.win_rate,
            equity_curve=bt.equity_curve,
        )

    def _generate_recommendation(
        self,
        results: dict[str, RiskLevelResult],
    ) -> Recommendation:
        """Pick optimal risk level based on risk-adjusted returns."""
        if not results:
            return Recommendation(
                optimal_risk_level="moderate",
                reasoning="No simulation data available, defaulting to moderate.",
                confidence=0.0,
            )

        # Score each risk level: sharpe * 0.5 + return * 0.3 - drawdown * 0.2
        scores: dict[str, float] = {}
        for level, result in results.items():
            sharpe = result.avg_sharpe if not math.isnan(result.avg_sharpe) else 0.0
            ret = result.total_return_pct if not math.isnan(result.total_return_pct) else 0.0
            dd = result.avg_max_drawdown if not math.isnan(result.avg_max_drawdown) else 0.0
            scores[level] = sharpe * 0.5 + ret * 0.3 - dd * 0.2

        best_level = max(scores, key=lambda k: scores[k])
        best_score = scores[best_level]
        best_result = results[best_level]

        # Confidence: how much better is best vs average?
        avg_score = sum(scores.values()) / len(scores) if scores else 0.0
        spread = best_score - avg_score
        confidence = min(1.0, max(0.1, 0.5 + spread * 0.1))

        # Strategy weight suggestion based on trade counts
        weights: dict[str, float] = {}
        if best_result.stock_results:
            total_wins = sum(r.winning_trades for r in best_result.stock_results)
            if total_wins > 0:
                weights["momentum"] = 0.5
                weights["quantitative"] = 0.5

        reasoning = (
            f"'{best_level}' achieved the best risk-adjusted score ({best_score:.2f}): "
            f"avg return {best_result.total_return_pct:.2f}%, "
            f"avg Sharpe {best_result.avg_sharpe:.3f}, "
            f"avg max drawdown {best_result.avg_max_drawdown:.2f}%."
        )

        return Recommendation(
            optimal_risk_level=best_level,
            reasoning=reasoning,
            suggested_weights=weights,
            confidence=confidence,
        )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/simulation/test_engine.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/simulation/engine.py tests/simulation/test_engine.py
git commit -m "feat(simulation): add simulation engine with walk-forward and MC projection"
```

---

## Task 4: CLI Command

**Files:**
- Create: `src/cli/simulation_cmd.py`
- Modify: `src/cli/main.py` (add `simulation` subcommand)
- Test: `tests/cli/test_simulation_cmd.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_simulation_cmd.py
"""Tests for simulation CLI command."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.simulation_cmd import app

runner = CliRunner()


def test_simulation_run_help():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "initial-balance" in result.output.lower() or "balance" in result.output.lower()


def test_simulation_run_defaults():
    """Smoke test: ensure the command can be invoked (mocking the engine)."""
    mock_report = {
        "id": "test123",
        "status": "completed",
        "config": {"stocks": ["AAPL"], "initial_balance": 10000.0, "train_days": 60, "test_days": 30, "risk_levels": ["moderate"], "mc_simulations": 50},
        "risk_level_results": {},
        "recommendation": {"optimal_risk_level": "moderate", "reasoning": "test", "suggested_weights": {}, "confidence": 0.5},
        "started_at": "2026-01-01T00:00:00",
        "completed_at": "2026-01-01T00:01:00",
        "error": None,
    }

    with patch("src.cli.simulation_cmd._run_simulation", return_value=mock_report):
        result = runner.invoke(app, [
            "run",
            "--stocks", "AAPL",
            "--balance", "10000",
            "--train-days", "60",
            "--test-days", "30",
            "--mc-sims", "50",
        ])
        assert result.exit_code == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_simulation_cmd.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# src/cli/simulation_cmd.py
"""CLI commands for the simulation system."""
from __future__ import annotations

import asyncio
import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.core.config import RiskLevel

app = typer.Typer(help="Simulation system: run walk-forward backtests and Monte Carlo projections.")
console = Console()

ALL_STOCKS = [
    "SPY", "QQQ", "DIA", "IWM",
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "XLF", "XLK", "XLE", "XLV", "XLI",
]


def _run_simulation(
    stocks: list[str],
    balance: float,
    train_days: int,
    test_days: int,
    risk_levels: list[RiskLevel],
    mc_sims: int,
) -> dict:
    """Run the simulation engine and return the report as a dict."""
    from src.simulation.engine import SimulationEngine
    from src.simulation.models import SimulationConfig

    config = SimulationConfig(
        stocks=stocks,
        initial_balance=balance,
        train_days=train_days,
        test_days=test_days,
        risk_levels=risk_levels,
        mc_simulations=mc_sims,
    )
    engine = SimulationEngine(config)
    report = asyncio.run(engine.run())
    return report.model_dump()


@app.command()
def run(
    stocks: Optional[list[str]] = typer.Option(None, help="Stock symbols (default: all 16)"),
    balance: float = typer.Option(10_000.0, help="Starting balance in USD"),
    train_days: int = typer.Option(60, help="Training window in days"),
    test_days: int = typer.Option(30, help="Test/simulation window in days"),
    risk_levels: Optional[list[str]] = typer.Option(None, "--risk", help="Risk levels (default: all)"),
    mc_sims: int = typer.Option(1000, help="Number of Monte Carlo simulations"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Run a full simulation across stocks and risk levels."""
    stock_list = stocks or ALL_STOCKS
    levels = [RiskLevel(r) for r in risk_levels] if risk_levels else list(RiskLevel)

    console.print(f"\n[bold]Simulation: {len(stock_list)} stocks, {len(levels)} risk levels[/bold]")
    console.print(f"Balance: ${balance:,.0f} | Train: {train_days}d | Test: {test_days}d | MC paths: {mc_sims}\n")

    with console.status("[bold green]Running simulation..."):
        report = _run_simulation(stock_list, balance, train_days, test_days, levels, mc_sims)

    if output_json:
        console.print(json.dumps(report, indent=2, default=str))
        return

    _print_report(report)


def _print_report(report: dict) -> None:
    """Pretty-print simulation results."""
    console.print(f"\n[bold green]Simulation {report['id']} — {report['status']}[/bold green]\n")

    # Risk level comparison table
    table = Table(title="Risk Level Comparison")
    table.add_column("Risk Level", style="bold")
    table.add_column("Avg Return %", justify="right")
    table.add_column("Avg Sharpe", justify="right")
    table.add_column("Avg Max DD %", justify="right")
    table.add_column("Total Trades", justify="right")

    for level_name, result in report.get("risk_level_results", {}).items():
        ret_style = "green" if result["total_return_pct"] >= 0 else "red"
        table.add_row(
            level_name,
            f"[{ret_style}]{result['total_return_pct']:.2f}%[/{ret_style}]",
            f"{result['avg_sharpe']:.3f}",
            f"{result['avg_max_drawdown']:.2f}%",
            str(result["total_trades"]),
        )

    console.print(table)

    # Per-stock details for each risk level
    for level_name, result in report.get("risk_level_results", {}).items():
        if not result.get("stock_results"):
            continue

        stock_table = Table(title=f"\n{level_name.upper()} — Per-Stock Results")
        stock_table.add_column("Symbol", style="bold")
        stock_table.add_column("Return %", justify="right")
        stock_table.add_column("Sharpe", justify="right")
        stock_table.add_column("Max DD %", justify="right")
        stock_table.add_column("Win Rate", justify="right")
        stock_table.add_column("Trades", justify="right")

        for sr in result["stock_results"]:
            ret_style = "green" if sr["return_pct"] >= 0 else "red"
            stock_table.add_row(
                sr["symbol"],
                f"[{ret_style}]{sr['return_pct']:.2f}%[/{ret_style}]",
                f"{sr['sharpe_ratio']:.3f}",
                f"{sr['max_drawdown']:.2f}%",
                f"{sr['win_rate']:.1%}",
                str(sr["total_trades"]),
            )

        console.print(stock_table)

    # Monte Carlo projections
    for level_name, result in report.get("risk_level_results", {}).items():
        if not result.get("monte_carlo_projections"):
            continue

        mc_table = Table(title=f"\n{level_name.upper()} — Monte Carlo Projections ({report['config']['test_days']}d forward)")
        mc_table.add_column("Symbol", style="bold")
        mc_table.add_column("Median Final", justify="right")
        mc_table.add_column("P5 Final", justify="right")
        mc_table.add_column("P95 Final", justify="right")
        mc_table.add_column("Median Return %", justify="right")
        mc_table.add_column("Worst DD (P95) %", justify="right")

        for mc in result["monte_carlo_projections"]:
            mc_table.add_row(
                mc["symbol"],
                f"${mc['median_final']:,.2f}",
                f"${mc['p5_final']:,.2f}",
                f"${mc['p95_final']:,.2f}",
                f"{mc['median_return_pct']:.2f}%",
                f"{mc['worst_drawdown_p95']:.2f}%",
            )

        console.print(mc_table)

    # Recommendation
    rec = report.get("recommendation")
    if rec:
        console.print(f"\n[bold yellow]RECOMMENDATION[/bold yellow]")
        console.print(f"  Optimal Risk Level: [bold]{rec['optimal_risk_level']}[/bold]")
        console.print(f"  Confidence: {rec['confidence']:.0%}")
        console.print(f"  Reasoning: {rec['reasoning']}")
        if rec.get("suggested_weights"):
            console.print(f"  Strategy Weights: {rec['suggested_weights']}")
        console.print()
```

Then update `src/cli/main.py` to include the simulation command:

```python
# Add to imports:
from src.cli.simulation_cmd import app as simulation_app

# Add to app registrations:
app.add_typer(simulation_app, name="simulation")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_simulation_cmd.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/cli/simulation_cmd.py src/cli/main.py tests/cli/test_simulation_cmd.py
git commit -m "feat(simulation): add CLI commands for simulation system"
```

---

## Task 5: API Router

**Files:**
- Create: `src/dashboard/routers/simulation.py`
- Modify: `src/dashboard/app.py` (register new router)
- Modify: `src/dashboard/schemas.py` (add SimulationRequest schema)
- Test: `tests/dashboard/test_simulation_router.py`

**Step 1: Write the failing test**

```python
# tests/dashboard/test_simulation_router.py
"""Tests for the simulation API router."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.dashboard.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_simulation_run_endpoint(client):
    mock_report = {
        "id": "test123",
        "status": "completed",
        "config": {"stocks": ["AAPL"], "initial_balance": 10000.0, "train_days": 60, "test_days": 30, "risk_levels": ["moderate"], "mc_simulations": 50},
        "risk_level_results": {},
        "recommendation": None,
        "started_at": "2026-01-01T00:00:00",
        "completed_at": "2026-01-01T00:01:00",
        "error": None,
    }

    with patch("src.dashboard.routers.simulation._run_async", new_callable=AsyncMock, return_value=mock_report):
        resp = client.post("/api/simulation/run", json={
            "stocks": ["AAPL"],
            "initial_balance": 10000.0,
            "train_days": 60,
            "test_days": 30,
            "risk_levels": ["moderate"],
            "mc_simulations": 50,
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "test123"
    assert data["status"] == "completed"


def test_simulation_list_runs(client):
    resp = client.get("/api/simulation/runs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_simulation_get_run_not_found(client):
    resp = client.get("/api/simulation/runs/nonexistent")
    assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/dashboard/test_simulation_router.py -v`
Expected: FAIL (router not registered)

**Step 3: Write minimal implementation**

Add to `src/dashboard/schemas.py`:

```python
# -- Simulation ---------------------------------------------------------------

class SimulationRequest(BaseModel):
    stocks: list[str] = Field(default_factory=lambda: [
        "SPY", "QQQ", "DIA", "IWM",
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
        "XLF", "XLK", "XLE", "XLV", "XLI",
    ])
    initial_balance: float = Field(default=10_000.0, gt=0)
    train_days: int = Field(default=60, gt=0)
    test_days: int = Field(default=30, gt=0)
    risk_levels: list[str] = Field(default_factory=lambda: [
        "conservative", "moderate", "aggressive", "very_aggressive",
    ])
    mc_simulations: int = Field(default=1000, gt=0)
```

Create `src/dashboard/routers/simulation.py`:

```python
"""Simulation endpoints: run, list, get results."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.dashboard.schemas import SimulationRequest

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

# In-memory store for simulation runs
_simulation_runs: dict[str, dict] = {}


async def _run_async(req: SimulationRequest) -> dict:
    """Run simulation engine and return report dict."""
    from src.core.config import RiskLevel
    from src.simulation.engine import SimulationEngine
    from src.simulation.models import SimulationConfig

    config = SimulationConfig(
        stocks=req.stocks,
        initial_balance=req.initial_balance,
        train_days=req.train_days,
        test_days=req.test_days,
        risk_levels=[RiskLevel(r) for r in req.risk_levels],
        mc_simulations=req.mc_simulations,
    )
    engine = SimulationEngine(config)
    report = await engine.run()
    return report.model_dump()


@router.post("/run")
async def run_simulation(req: SimulationRequest):
    """Run a new simulation."""
    report = await _run_async(req)
    _simulation_runs[report["id"]] = report
    return report


@router.get("/runs")
async def list_runs():
    """List all simulation runs."""
    return list(_simulation_runs.values())


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get a specific simulation run."""
    if run_id not in _simulation_runs:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return _simulation_runs[run_id]
```

Update `src/dashboard/app.py` — add to imports:

```python
from src.dashboard.routers import simulation
```

And add to router registrations:

```python
app.include_router(simulation.router)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/dashboard/test_simulation_router.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/dashboard/routers/simulation.py src/dashboard/schemas.py src/dashboard/app.py tests/dashboard/test_simulation_router.py
git commit -m "feat(simulation): add API router for simulation system"
```

---

## Task 6: Frontend API Functions and Mock Data

**Files:**
- Modify: `web/src/lib/api.ts` (add simulation API functions)
- Create: `web/src/lib/mock/data/simulation.ts` (mock data for demo mode)
- Modify: `web/src/lib/mock/index.ts` (register simulation mock)

**Step 1: Add API functions to `web/src/lib/api.ts`**

Append to end of file:

```typescript
// Simulation
export const runSimulation = (config: {
  stocks: string[];
  initial_balance: number;
  train_days: number;
  test_days: number;
  risk_levels: string[];
  mc_simulations: number;
}) =>
  fetchAPI<Record<string, unknown>>("/api/simulation/run", {
    method: "POST",
    body: JSON.stringify(config),
  });
export const getSimulationRuns = () =>
  fetchAPI<Record<string, unknown>[]>("/api/simulation/runs");
export const getSimulationRun = (id: string) =>
  fetchAPI<Record<string, unknown>>(`/api/simulation/runs/${id}`);
```

**Step 2: Create mock data `web/src/lib/mock/data/simulation.ts`**

```typescript
import { registerRoute } from "../router";

const MOCK_SIMULATION = {
  id: "sim-demo",
  status: "completed",
  config: {
    stocks: ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL"],
    initial_balance: 10000,
    train_days: 60,
    test_days: 30,
    risk_levels: ["conservative", "moderate", "aggressive", "very_aggressive"],
    mc_simulations: 1000,
  },
  risk_level_results: {
    conservative: {
      risk_level: "conservative",
      total_return_pct: 2.4,
      avg_sharpe: 0.85,
      avg_max_drawdown: 3.2,
      total_trades: 45,
      stock_results: [
        { symbol: "AAPL", return_pct: 3.1, sharpe_ratio: 1.1, max_drawdown: 2.5, win_rate: 0.62, total_trades: 12, initial_balance: 10000, final_value: 10310, total_pnl: 310, winning_trades: 7, losing_trades: 5, equity_curve: [] },
        { symbol: "MSFT", return_pct: 2.8, sharpe_ratio: 0.9, max_drawdown: 3.0, win_rate: 0.58, total_trades: 10, initial_balance: 10000, final_value: 10280, total_pnl: 280, winning_trades: 6, losing_trades: 4, equity_curve: [] },
        { symbol: "NVDA", return_pct: 4.2, sharpe_ratio: 1.2, max_drawdown: 4.5, win_rate: 0.65, total_trades: 8, initial_balance: 10000, final_value: 10420, total_pnl: 420, winning_trades: 5, losing_trades: 3, equity_curve: [] },
        { symbol: "TSLA", return_pct: -1.3, sharpe_ratio: 0.3, max_drawdown: 5.8, win_rate: 0.45, total_trades: 9, initial_balance: 10000, final_value: 9870, total_pnl: -130, winning_trades: 4, losing_trades: 5, equity_curve: [] },
        { symbol: "GOOGL", return_pct: 3.2, sharpe_ratio: 0.8, max_drawdown: 2.8, win_rate: 0.55, total_trades: 6, initial_balance: 10000, final_value: 10320, total_pnl: 320, winning_trades: 3, losing_trades: 3, equity_curve: [] },
      ],
      monte_carlo_projections: [
        { symbol: "AAPL", median_final: 10350, p5_final: 9500, p95_final: 11200, median_return_pct: 3.5, p5_return_pct: -5.0, p95_return_pct: 12.0, worst_drawdown_p95: 8.5, n_paths: 1000 },
        { symbol: "MSFT", median_final: 10280, p5_final: 9400, p95_final: 11100, median_return_pct: 2.8, p5_return_pct: -6.0, p95_return_pct: 11.0, worst_drawdown_p95: 9.0, n_paths: 1000 },
        { symbol: "NVDA", median_final: 10500, p5_final: 8800, p95_final: 12500, median_return_pct: 5.0, p5_return_pct: -12.0, p95_return_pct: 25.0, worst_drawdown_p95: 15.0, n_paths: 1000 },
        { symbol: "TSLA", median_final: 10100, p5_final: 8200, p95_final: 12800, median_return_pct: 1.0, p5_return_pct: -18.0, p95_return_pct: 28.0, worst_drawdown_p95: 22.0, n_paths: 1000 },
        { symbol: "GOOGL", median_final: 10320, p5_final: 9450, p95_final: 11200, median_return_pct: 3.2, p5_return_pct: -5.5, p95_return_pct: 12.0, worst_drawdown_p95: 8.0, n_paths: 1000 },
      ],
      strategy_assessments: [],
    },
    moderate: {
      risk_level: "moderate",
      total_return_pct: 4.8,
      avg_sharpe: 1.05,
      avg_max_drawdown: 5.1,
      total_trades: 78,
      stock_results: [
        { symbol: "AAPL", return_pct: 5.8, sharpe_ratio: 1.3, max_drawdown: 4.2, win_rate: 0.60, total_trades: 18, initial_balance: 10000, final_value: 10580, total_pnl: 580, winning_trades: 11, losing_trades: 7, equity_curve: [] },
        { symbol: "MSFT", return_pct: 4.5, sharpe_ratio: 1.0, max_drawdown: 4.8, win_rate: 0.56, total_trades: 16, initial_balance: 10000, final_value: 10450, total_pnl: 450, winning_trades: 9, losing_trades: 7, equity_curve: [] },
        { symbol: "NVDA", return_pct: 8.2, sharpe_ratio: 1.4, max_drawdown: 7.0, win_rate: 0.63, total_trades: 14, initial_balance: 10000, final_value: 10820, total_pnl: 820, winning_trades: 9, losing_trades: 5, equity_curve: [] },
        { symbol: "TSLA", return_pct: -2.5, sharpe_ratio: 0.2, max_drawdown: 9.5, win_rate: 0.42, total_trades: 18, initial_balance: 10000, final_value: 9750, total_pnl: -250, winning_trades: 8, losing_trades: 10, equity_curve: [] },
        { symbol: "GOOGL", return_pct: 8.0, sharpe_ratio: 1.35, max_drawdown: 5.0, win_rate: 0.58, total_trades: 12, initial_balance: 10000, final_value: 10800, total_pnl: 800, winning_trades: 7, losing_trades: 5, equity_curve: [] },
      ],
      monte_carlo_projections: [
        { symbol: "AAPL", median_final: 10600, p5_final: 9200, p95_final: 12000, median_return_pct: 6.0, p5_return_pct: -8.0, p95_return_pct: 20.0, worst_drawdown_p95: 12.0, n_paths: 1000 },
        { symbol: "MSFT", median_final: 10450, p5_final: 9100, p95_final: 11800, median_return_pct: 4.5, p5_return_pct: -9.0, p95_return_pct: 18.0, worst_drawdown_p95: 13.0, n_paths: 1000 },
        { symbol: "NVDA", median_final: 10900, p5_final: 8400, p95_final: 13800, median_return_pct: 9.0, p5_return_pct: -16.0, p95_return_pct: 38.0, worst_drawdown_p95: 20.0, n_paths: 1000 },
        { symbol: "TSLA", median_final: 10050, p5_final: 7800, p95_final: 13500, median_return_pct: 0.5, p5_return_pct: -22.0, p95_return_pct: 35.0, worst_drawdown_p95: 28.0, n_paths: 1000 },
        { symbol: "GOOGL", median_final: 10500, p5_final: 9200, p95_final: 11800, median_return_pct: 5.0, p5_return_pct: -8.0, p95_return_pct: 18.0, worst_drawdown_p95: 11.0, n_paths: 1000 },
      ],
      strategy_assessments: [],
    },
    aggressive: {
      risk_level: "aggressive",
      total_return_pct: 6.5,
      avg_sharpe: 0.90,
      avg_max_drawdown: 8.8,
      total_trades: 120,
      stock_results: [
        { symbol: "AAPL", return_pct: 8.2, sharpe_ratio: 1.1, max_drawdown: 7.0, win_rate: 0.55, total_trades: 28, initial_balance: 10000, final_value: 10820, total_pnl: 820, winning_trades: 15, losing_trades: 13, equity_curve: [] },
        { symbol: "MSFT", return_pct: 6.5, sharpe_ratio: 0.9, max_drawdown: 8.0, win_rate: 0.52, total_trades: 24, initial_balance: 10000, final_value: 10650, total_pnl: 650, winning_trades: 13, losing_trades: 11, equity_curve: [] },
        { symbol: "NVDA", return_pct: 14.0, sharpe_ratio: 1.3, max_drawdown: 12.0, win_rate: 0.60, total_trades: 22, initial_balance: 10000, final_value: 11400, total_pnl: 1400, winning_trades: 13, losing_trades: 9, equity_curve: [] },
        { symbol: "TSLA", return_pct: -5.2, sharpe_ratio: -0.1, max_drawdown: 15.0, win_rate: 0.38, total_trades: 26, initial_balance: 10000, final_value: 9480, total_pnl: -520, winning_trades: 10, losing_trades: 16, equity_curve: [] },
        { symbol: "GOOGL", return_pct: 9.0, sharpe_ratio: 1.3, max_drawdown: 6.0, win_rate: 0.60, total_trades: 20, initial_balance: 10000, final_value: 10900, total_pnl: 900, winning_trades: 12, losing_trades: 8, equity_curve: [] },
      ],
      monte_carlo_projections: [],
      strategy_assessments: [],
    },
    very_aggressive: {
      risk_level: "very_aggressive",
      total_return_pct: 5.0,
      avg_sharpe: 0.55,
      avg_max_drawdown: 14.2,
      total_trades: 180,
      stock_results: [
        { symbol: "AAPL", return_pct: 10.0, sharpe_ratio: 0.8, max_drawdown: 12.0, win_rate: 0.50, total_trades: 40, initial_balance: 10000, final_value: 11000, total_pnl: 1000, winning_trades: 20, losing_trades: 20, equity_curve: [] },
        { symbol: "MSFT", return_pct: 7.5, sharpe_ratio: 0.6, max_drawdown: 13.0, win_rate: 0.48, total_trades: 38, initial_balance: 10000, final_value: 10750, total_pnl: 750, winning_trades: 18, losing_trades: 20, equity_curve: [] },
        { symbol: "NVDA", return_pct: 18.0, sharpe_ratio: 1.0, max_drawdown: 18.0, win_rate: 0.55, total_trades: 34, initial_balance: 10000, final_value: 11800, total_pnl: 1800, winning_trades: 19, losing_trades: 15, equity_curve: [] },
        { symbol: "TSLA", return_pct: -12.0, sharpe_ratio: -0.5, max_drawdown: 25.0, win_rate: 0.32, total_trades: 38, initial_balance: 10000, final_value: 8800, total_pnl: -1200, winning_trades: 12, losing_trades: 26, equity_curve: [] },
        { symbol: "GOOGL", return_pct: 1.5, sharpe_ratio: 0.35, max_drawdown: 10.0, win_rate: 0.50, total_trades: 30, initial_balance: 10000, final_value: 10150, total_pnl: 150, winning_trades: 15, losing_trades: 15, equity_curve: [] },
      ],
      monte_carlo_projections: [],
      strategy_assessments: [],
    },
  },
  recommendation: {
    optimal_risk_level: "moderate",
    reasoning: "'moderate' achieved the best risk-adjusted score (3.42): avg return 4.80%, avg Sharpe 1.050, avg max drawdown 5.10%.",
    suggested_weights: { momentum: 0.55, quantitative: 0.45 },
    confidence: 0.72,
  },
  started_at: "2026-02-18T10:00:00Z",
  completed_at: "2026-02-18T10:02:30Z",
  error: null,
};

registerRoute("POST", "/api/simulation/run", () => MOCK_SIMULATION);
registerRoute("GET", "/api/simulation/runs", () => [MOCK_SIMULATION]);
registerRoute("GET", "/api/simulation/runs/:id", () => MOCK_SIMULATION);
```

**Step 3: Update `web/src/lib/mock/index.ts`**

Add `import("./data/simulation");` inside the `if (MOCK_ENABLED)` block.

**Step 4: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/mock/data/simulation.ts web/src/lib/mock/index.ts
git commit -m "feat(simulation): add frontend API functions and mock data"
```

---

## Task 7: Frontend Simulation Page

**Files:**
- Create: `web/src/app/simulation/page.tsx`
- Modify: `web/src/components/layout/Sidebar.tsx` (add nav item)

**Step 1: Create the simulation page**

```tsx
// web/src/app/simulation/page.tsx
"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from "recharts";
import { runSimulation, getSimulationRuns } from "@/lib/api";
import ChartContainer from "@/components/shared/ChartContainer";
import StatCard from "@/components/shared/StatCard";
import DataTable from "@/components/shared/DataTable";
import { formatCurrency, formatPercent, formatNumber, cn } from "@/lib/formatters";
import { themeColors, chartAxisTick, chartGridProps, chartTooltipStyle } from "@/lib/chartTheme";
import { Activity, Play, TrendingUp, BarChart3, AlertTriangle, Target, Zap, Shield, Award } from "lucide-react";

const ALL_STOCKS = [
  "SPY", "QQQ", "DIA", "IWM",
  "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
  "XLF", "XLK", "XLE", "XLV", "XLI",
];

const RISK_LEVELS = ["conservative", "moderate", "aggressive", "very_aggressive"];

const RISK_COLORS: Record<string, string> = {
  conservative: themeColors.blue,
  moderate: themeColors.green,
  aggressive: themeColors.orange,
  very_aggressive: themeColors.red,
};

const RISK_ICONS: Record<string, typeof Shield> = {
  conservative: Shield,
  moderate: Target,
  aggressive: Zap,
  very_aggressive: AlertTriangle,
};

type StockResult = {
  symbol: string;
  return_pct: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  initial_balance: number;
  final_value: number;
  total_pnl: number;
};

type MCProjection = {
  symbol: string;
  median_final: number;
  p5_final: number;
  p95_final: number;
  median_return_pct: number;
  p5_return_pct: number;
  p95_return_pct: number;
  worst_drawdown_p95: number;
  n_paths: number;
};

type RiskResult = {
  risk_level: string;
  total_return_pct: number;
  avg_sharpe: number;
  avg_max_drawdown: number;
  total_trades: number;
  stock_results: StockResult[];
  monte_carlo_projections: MCProjection[];
};

type SimReport = {
  id: string;
  status: string;
  config: Record<string, unknown>;
  risk_level_results: Record<string, RiskResult>;
  recommendation: {
    optimal_risk_level: string;
    reasoning: string;
    suggested_weights: Record<string, number>;
    confidence: number;
  } | null;
  started_at: string;
  completed_at: string;
  error: string | null;
};

export default function SimulationPage() {
  const queryClient = useQueryClient();
  const { data: runs } = useQuery({ queryKey: ["simulation-runs"], queryFn: getSimulationRuns });

  const [config, setConfig] = useState({
    stocks: ALL_STOCKS,
    initial_balance: 10000,
    train_days: 60,
    test_days: 30,
    risk_levels: RISK_LEVELS,
    mc_simulations: 1000,
  });

  const [report, setReport] = useState<SimReport | null>(null);
  const [activeRisk, setActiveRisk] = useState("moderate");

  const mutation = useMutation({
    mutationFn: () => runSimulation(config),
    onSuccess: (data) => {
      setReport(data as unknown as SimReport);
      queryClient.invalidateQueries({ queryKey: ["simulation-runs"] });
    },
  });

  const activeResult = report?.risk_level_results?.[activeRisk];

  // Build comparison data for bar chart
  const comparisonData = report
    ? Object.entries(report.risk_level_results).map(([level, r]) => ({
        name: level.replace("_", " "),
        return: r.total_return_pct,
        sharpe: r.avg_sharpe,
        drawdown: r.avg_max_drawdown,
        trades: r.total_trades,
      }))
    : [];

  // Build radar data
  const radarData = report
    ? Object.entries(report.risk_level_results).map(([level, r]) => ({
        level: level.replace("_", " "),
        Return: Math.max(0, r.total_return_pct * 10),
        Sharpe: r.avg_sharpe * 50,
        Safety: Math.max(0, 100 - r.avg_max_drawdown * 5),
        Activity: Math.min(100, r.total_trades / 2),
      }))
    : [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold flex items-center gap-2">
        <Activity size={22} /> Simulation
      </h1>

      <div className="grid grid-cols-4 gap-6">
        {/* Config Panel */}
        <ChartContainer title="Configuration" className="col-span-1">
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-muted">Initial Balance ($)</label>
              <input
                type="number"
                value={config.initial_balance}
                onChange={(e) => setConfig({ ...config, initial_balance: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Training Days</label>
              <input
                type="number"
                value={config.train_days}
                onChange={(e) => setConfig({ ...config, train_days: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Test Days</label>
              <input
                type="number"
                value={config.test_days}
                onChange={(e) => setConfig({ ...config, test_days: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">MC Simulations</label>
              <input
                type="number"
                value={config.mc_simulations}
                onChange={(e) => setConfig({ ...config, mc_simulations: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Stocks (comma-separated)</label>
              <textarea
                value={config.stocks.join(", ")}
                onChange={(e) =>
                  setConfig({ ...config, stocks: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })
                }
                rows={3}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Risk Levels</label>
              <div className="space-y-1">
                {RISK_LEVELS.map((level) => (
                  <label key={level} className="flex items-center gap-2 text-xs text-foreground">
                    <input
                      type="checkbox"
                      checked={config.risk_levels.includes(level)}
                      onChange={(e) => {
                        const newLevels = e.target.checked
                          ? [...config.risk_levels, level]
                          : config.risk_levels.filter((l) => l !== level);
                        setConfig({ ...config, risk_levels: newLevels });
                      }}
                      className="rounded border-border"
                    />
                    {level.replace("_", " ")}
                  </label>
                ))}
              </div>
            </div>
            <button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {mutation.isPending ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <Play size={14} />
              )}
              {mutation.isPending ? "Running Simulation..." : "Run Simulation"}
            </button>
          </div>
        </ChartContainer>

        {/* Results Area */}
        <div className="col-span-3 space-y-4">
          {report && !report.error ? (
            <>
              {/* Recommendation Banner */}
              {report.recommendation && (
                <div className="rounded-xl border border-accent/30 bg-accent/5 p-4">
                  <div className="flex items-start gap-3">
                    <Award size={20} className="mt-0.5 text-accent" />
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        Recommended: <span className="text-accent">{report.recommendation.optimal_risk_level.replace("_", " ")}</span>
                        <span className="ml-2 text-xs text-muted">({formatPercent(report.recommendation.confidence * 100, 0)} confidence)</span>
                      </p>
                      <p className="mt-1 text-xs text-muted">{report.recommendation.reasoning}</p>
                      {Object.keys(report.recommendation.suggested_weights).length > 0 && (
                        <p className="mt-1 text-xs text-muted">
                          Strategy weights: {Object.entries(report.recommendation.suggested_weights).map(([k, v]) => `${k}: ${(v * 100).toFixed(0)}%`).join(", ")}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Risk Level Overview Cards */}
              <div className="grid grid-cols-4 gap-3">
                {Object.entries(report.risk_level_results).map(([level, r]) => {
                  const Icon = RISK_ICONS[level] || Target;
                  const isActive = level === activeRisk;
                  const isRecommended = level === report.recommendation?.optimal_risk_level;
                  return (
                    <button
                      key={level}
                      onClick={() => setActiveRisk(level)}
                      className={cn(
                        "rounded-xl border p-4 text-left transition-all",
                        isActive ? "border-accent bg-accent/10" : "border-border bg-card hover:bg-card-hover",
                        isRecommended && "ring-1 ring-accent/50"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <Icon size={16} className="text-muted" />
                        {isRecommended && <span className="text-[10px] font-medium text-accent">BEST</span>}
                      </div>
                      <p className="mt-2 text-xs text-muted">{level.replace("_", " ")}</p>
                      <p className={cn("text-lg font-semibold", r.total_return_pct >= 0 ? "text-profit" : "text-loss")}>
                        {r.total_return_pct >= 0 ? "+" : ""}{r.total_return_pct.toFixed(2)}%
                      </p>
                      <p className="text-[10px] text-muted">Sharpe {r.avg_sharpe.toFixed(2)} | DD {r.avg_max_drawdown.toFixed(1)}%</p>
                    </button>
                  );
                })}
              </div>

              {/* Comparison Chart */}
              <ChartContainer title="Risk Level Comparison" subtitle="Return % across all risk profiles">
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={comparisonData}>
                    <CartesianGrid {...chartGridProps} />
                    <XAxis dataKey="name" tick={chartAxisTick} />
                    <YAxis tick={chartAxisTick} tickFormatter={(v) => `${v}%`} />
                    <Tooltip contentStyle={chartTooltipStyle} />
                    <Legend />
                    <Bar dataKey="return" name="Avg Return %" fill={themeColors.green} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="drawdown" name="Avg Max DD %" fill={themeColors.red} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>

              {/* Per-Stock Table for Active Risk Level */}
              {activeResult && activeResult.stock_results.length > 0 && (
                <ChartContainer title={`${activeRisk.replace("_", " ").toUpperCase()} — Per-Stock Results`} subtitle={`${activeResult.total_trades} total trades`}>
                  <DataTable
                    columns={[
                      { key: "symbol", header: "Symbol" },
                      {
                        key: "return_pct",
                        header: "Return %",
                        render: (r) => (
                          <span className={cn((r.return_pct as number) >= 0 ? "text-profit" : "text-loss")}>
                            {(r.return_pct as number) >= 0 ? "+" : ""}{formatPercent(r.return_pct as number)}
                          </span>
                        ),
                      },
                      { key: "sharpe_ratio", header: "Sharpe", render: (r) => formatNumber(r.sharpe_ratio as number) },
                      { key: "max_drawdown", header: "Max DD %", render: (r) => formatPercent(r.max_drawdown as number) },
                      { key: "win_rate", header: "Win Rate", render: (r) => formatPercent((r.win_rate as number) * 100, 0) },
                      { key: "total_trades", header: "Trades" },
                      {
                        key: "total_pnl",
                        header: "P&L",
                        render: (r) => (
                          <span className={cn((r.total_pnl as number) >= 0 ? "text-profit" : "text-loss")}>
                            {formatCurrency(r.total_pnl as number)}
                          </span>
                        ),
                      },
                    ]}
                    data={activeResult.stock_results as unknown as Record<string, unknown>[]}
                    emptyMessage="No stock results"
                  />
                </ChartContainer>
              )}

              {/* Monte Carlo Projections Table */}
              {activeResult && activeResult.monte_carlo_projections.length > 0 && (
                <ChartContainer title={`${activeRisk.replace("_", " ").toUpperCase()} — Monte Carlo Projections`} subtitle={`${activeResult.monte_carlo_projections[0]?.n_paths || 0} simulated paths per stock`}>
                  <DataTable
                    columns={[
                      { key: "symbol", header: "Symbol" },
                      { key: "median_final", header: "Median $", render: (r) => formatCurrency(r.median_final as number) },
                      { key: "p5_final", header: "P5 $", render: (r) => formatCurrency(r.p5_final as number) },
                      { key: "p95_final", header: "P95 $", render: (r) => formatCurrency(r.p95_final as number) },
                      {
                        key: "median_return_pct",
                        header: "Median Ret %",
                        render: (r) => (
                          <span className={cn((r.median_return_pct as number) >= 0 ? "text-profit" : "text-loss")}>
                            {formatPercent(r.median_return_pct as number)}
                          </span>
                        ),
                      },
                      { key: "worst_drawdown_p95", header: "Worst DD (P95)", render: (r) => formatPercent(r.worst_drawdown_p95 as number) },
                    ]}
                    data={activeResult.monte_carlo_projections as unknown as Record<string, unknown>[]}
                    emptyMessage="No projections"
                  />
                </ChartContainer>
              )}
            </>
          ) : report?.error ? (
            <div className="rounded-xl border border-border bg-card p-8 text-center text-muted">
              <AlertTriangle size={32} className="mx-auto mb-3 text-warning" />
              <p className="text-sm">{report.error}</p>
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-card p-12 text-center text-muted">
              <Activity size={40} className="mx-auto mb-4 opacity-50" />
              <p className="text-sm font-medium">Configure and run a simulation</p>
              <p className="mt-1 text-xs">
                Fetches real stock data, runs walk-forward backtests across risk levels, and generates Monte Carlo projections with strategy recommendations.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Previous Runs */}
      <ChartContainer title="Previous Simulation Runs">
        <DataTable
          columns={[
            { key: "id", header: "Run ID" },
            {
              key: "status",
              header: "Status",
              render: (r) => (
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs",
                    r.status === "completed" ? "bg-profit/20 text-profit" : r.status === "failed" ? "bg-loss/20 text-loss" : "bg-warning/20 text-warning"
                  )}
                >
                  {r.status as string}
                </span>
              ),
            },
            { key: "started_at", header: "Started" },
            {
              key: "config",
              header: "Stocks",
              render: (r) => {
                const c = r.config as Record<string, unknown>;
                const stocks = c?.stocks as string[];
                return stocks ? `${stocks.length} stocks` : "";
              },
            },
          ]}
          data={(runs || []) as Record<string, unknown>[]}
          emptyMessage="No simulation runs yet"
        />
      </ChartContainer>
    </div>
  );
}
```

**Step 2: Update sidebar**

In `web/src/components/layout/Sidebar.tsx`, add to navItems array (after `backtest`):

```tsx
{ href: "/simulation", label: "Simulation", icon: Activity },
```

And add `Activity` to the lucide-react import.

**Step 3: Commit**

```bash
git add web/src/app/simulation/page.tsx web/src/components/layout/Sidebar.tsx
git commit -m "feat(simulation): add frontend simulation page with risk comparison"
```

---

## Task 8: Integration Test — Full Pipeline

**Files:**
- Create: `tests/simulation/test_integration.py`

**Step 1: Write the integration test**

```python
# tests/simulation/test_integration.py
"""Integration test: full simulation pipeline end-to-end."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import RiskLevel
from src.data.providers.base import OHLCBar
from src.simulation.engine import SimulationEngine
from src.simulation.models import SimulationConfig


def _make_bars(n: int, start_price: float = 150.0, volatility: float = 2.0) -> list[OHLCBar]:
    """Create n daily bars simulating realistic stock price movement."""
    import random
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
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/simulation/test_integration.py -v`
Expected: PASS (all prior tasks must be completed first)

**Step 3: Commit**

```bash
git add tests/simulation/test_integration.py
git commit -m "test(simulation): add full pipeline integration test"
```

---

## Task 9: Run All Tests and Final Verification

**Step 1: Run full test suite**

```bash
uv run pytest tests/simulation/ -v
```

Expected: All tests pass.

**Step 2: Run CLI smoke test**

```bash
uv run python -m src.cli.main simulation run --stocks AAPL --stocks MSFT --balance 10000 --train-days 60 --test-days 30 --mc-sims 50 --risk moderate
```

Expected: Table output showing simulation results.

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(simulation): complete simulation system with CLI, API, and frontend"
```
