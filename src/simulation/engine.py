"""Simulation engine: orchestrates data fetch, backtest, MC projection, and assessment."""

from __future__ import annotations

import logging
import math
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

import numpy as np

from src.core.config import RiskLevel, RiskSettings
from src.core.models import AssetType, MarketTick
from src.data.backtester import BacktestResult, run_backtest
from src.simulation.models import (
    MonteCarloProjection,
    PortfolioMonteCarloProjection,
    Recommendation,
    RiskLevelResult,
    SimulationConfig,
    SimulationReport,
    StockSimResult,
)
from src.simulation.portfolio import PortfolioSimulator
from src.simulation.projector import MonteCarloProjector

if TYPE_CHECKING:
    from src.data.providers.base import OHLCBar

logger = logging.getLogger(__name__)


class ProgressCallback(Protocol):
    """Callback for reporting simulation progress."""

    def __call__(self, stage: str, current: int, total: int, detail: str = "") -> None: ...


class SimulationEngine:
    """Run walk-forward backtests and Monte Carlo projections across risk levels."""

    def __init__(
        self,
        config: SimulationConfig,
        progress_cb: ProgressCallback | None = None,
        use_cache: bool = True,
    ) -> None:
        self._config = config
        self._progress_cb = progress_cb
        if use_cache:
            from src.simulation.cache import BarCache

            self._bar_cache: BarCache | None = BarCache()
        else:
            self._bar_cache = None

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
            num_levels = len(self._config.risk_levels)

            # Derive unique but deterministic child seeds per risk level
            # from a single parent RNG seeded with the user's mc_seed.
            parent_rng = np.random.default_rng(self._config.mc_seed)
            child_seeds = [int(parent_rng.integers(0, 2**31)) for _ in self._config.risk_levels]

            for i, risk_level in enumerate(self._config.risk_levels):
                if self._progress_cb:
                    self._progress_cb("risk_level", i + 1, num_levels, risk_level.value)
                result = await self._run_risk_level(
                    risk_level,
                    mc_seed=child_seeds[i],
                )
                risk_results[risk_level.value] = result

            report.risk_level_results = risk_results

            # Compute SPY benchmarks (once per simulation)
            if self._progress_cb:
                self._progress_cb("benchmark", 0, 0, "Computing SPY benchmarks")
            try:
                spy_bars = await self._fetch_bars("SPY")
                total_needed = self._config.train_days + self._config.test_days
                if len(spy_bars) >= total_needed:
                    test_bars = spy_bars[self._config.train_days : total_needed]
                else:
                    split = len(spy_bars) * 2 // 3
                    test_bars = spy_bars[split:]

                if test_bars:
                    from src.simulation.benchmark import BenchmarkSimulator

                    bench = BenchmarkSimulator()
                    report.benchmarks = {
                        "spy_buy_hold": bench.buy_and_hold(
                            test_bars,
                            self._config.initial_balance,
                        ),
                        "spy_dca": bench.monthly_dca(
                            test_bars,
                            self._config.initial_balance,
                        ),
                    }
            except Exception:
                logger.warning("Failed to compute SPY benchmarks", exc_info=True)

            report.recommendation = self._generate_recommendation(risk_results)
            report.status = "completed"
        except Exception as e:
            logger.exception("Simulation failed")
            report.status = "failed"
            report.error = str(e)

        report.completed_at = datetime.now(UTC).isoformat()
        return report

    async def _run_risk_level(
        self,
        risk_level: RiskLevel,
        *,
        mc_seed: int | None = None,
    ) -> RiskLevelResult:
        """Run simulation for one risk level across all stocks."""
        overrides: dict[str, float] = {}
        if self._config.max_position_pct is not None:
            overrides["max_position_pct"] = self._config.max_position_pct
        risk_settings = RiskSettings.from_risk_level(risk_level, **overrides)
        stock_results: list[StockSimResult] = []
        mc_projections: list[MonteCarloProjection] = []

        # Create portfolio simulator when in portfolio mode
        portfolio_sim: PortfolioSimulator | None = None
        if self._config.portfolio_mode:
            portfolio_sim = PortfolioSimulator(self._config)

        # Collect training prices per stock for correlated MC (portfolio mode)
        train_prices_per_stock: dict[str, list[float]] = {}

        num_stocks = len(self._config.stocks)
        for j, symbol in enumerate(self._config.stocks):
            bars = await self._fetch_bars(symbol)
            total_needed = self._config.train_days + self._config.test_days

            if len(bars) < 10:
                logger.warning("Insufficient data for %s: %d bars", symbol, len(bars))
                continue

            # Split into train and test
            if len(bars) >= total_needed:
                train_bars = bars[: self._config.train_days]
                test_bars = bars[self._config.train_days : total_needed]
            else:
                # Use what we have: 2/3 train, 1/3 test
                split = len(bars) * 2 // 3
                train_bars = bars[:split]
                test_bars = bars[split:]

            # Walk-forward backtest on test data
            ticks = self._bars_to_ticks(test_bars, symbol)
            if ticks:
                # Adapt SMA windows to fit available test data
                n_ticks = len(ticks)
                long_window = min(20, n_ticks // 2) if n_ticks < 50 else 50
                short_window = max(3, long_window // 3)
                # Lower z-threshold so quant strategy fires on daily data
                quant_z = 1.0 if n_ticks < 100 else 2.0
                # Use allocated balance per stock in portfolio mode
                if portfolio_sim is not None:
                    stock_balance = Decimal(str(portfolio_sim.get_stock_balance(symbol)))
                else:
                    stock_balance = Decimal(str(self._config.initial_balance))

                bt_result = await run_backtest(
                    ticks,
                    initial_cash=stock_balance,
                    short_window=short_window,
                    long_window=long_window,
                    quant_z_threshold=quant_z,
                    risk_settings=risk_settings,
                )
                stock_results.append(self._to_stock_result(symbol, bt_result))

            # Monte Carlo projection using training data
            train_prices = [float(b.close) for b in train_bars]
            if portfolio_sim is not None and len(train_prices) > 5:
                train_prices_per_stock[symbol] = train_prices
            if len(train_prices) > 5:
                projector = MonteCarloProjector(
                    n_paths=self._config.mc_simulations,
                    seed=mc_seed,
                )
                paths = projector.generate_paths(train_prices, self._config.test_days)
                # Use allocated balance per stock in portfolio mode
                if portfolio_sim is not None:
                    mc_balance = portfolio_sim.get_stock_balance(symbol)
                else:
                    mc_balance = self._config.initial_balance
                summary = projector.summarize(
                    paths,
                    mc_balance,
                    train_prices[-1],
                )
                mc_projections.append(
                    MonteCarloProjection(
                        symbol=symbol,
                        median_final=summary["median_final"],
                        p5_final=summary["p5_final"],
                        p95_final=summary["p95_final"],
                        median_return_pct=summary["median_return_pct"],
                        p5_return_pct=summary["p5_return_pct"],
                        p95_return_pct=summary["p95_return_pct"],
                        worst_drawdown_p95=summary["worst_drawdown_p95"],
                        n_paths=self._config.mc_simulations,
                    )
                )

            if self._progress_cb:
                self._progress_cb("stock", j + 1, num_stocks, symbol)

        # Aggregate metrics
        total_return = (
            sum(r.return_pct for r in stock_results) / len(stock_results) if stock_results else 0.0
        )
        avg_sharpe = (
            sum(r.sharpe_ratio for r in stock_results) / len(stock_results)
            if stock_results
            else 0.0
        )
        avg_dd = (
            sum(r.max_drawdown for r in stock_results) / len(stock_results)
            if stock_results
            else 0.0
        )
        total_trades = sum(r.total_trades for r in stock_results)

        # Build portfolio-level metrics when in portfolio mode
        portfolio_metrics = None
        if portfolio_sim is not None and stock_results:
            stock_equity_curves: dict[str, list[float]] = {
                r.symbol: r.equity_curve for r in stock_results
            }
            portfolio_curve, rebalance_days = portfolio_sim.build_portfolio_equity_curve(
                stock_equity_curves
            )
            if portfolio_curve:
                portfolio_metrics = portfolio_sim.compute_portfolio_metrics(
                    portfolio_curve,
                    total_trades,
                    rebalance_days=rebalance_days,
                )

        # Correlated Monte Carlo for portfolio mode
        portfolio_mc: PortfolioMonteCarloProjection | None = None
        if portfolio_sim is not None and len(train_prices_per_stock) > 0:
            projector = MonteCarloProjector(
                n_paths=self._config.mc_simulations,
                seed=mc_seed,
            )
            portfolio_paths, corr_matrix = projector.generate_correlated_portfolio_paths(
                historical_prices=train_prices_per_stock,
                days_forward=self._config.test_days,
                weights=portfolio_sim.weights,
                initial_balance=self._config.initial_balance,
            )
            pmc_summary = projector.summarize_portfolio_paths(
                portfolio_paths,
                self._config.initial_balance,
            )
            portfolio_mc = PortfolioMonteCarloProjection(
                median_final=pmc_summary["median_final"],
                p5_final=pmc_summary["p5_final"],
                p95_final=pmc_summary["p95_final"],
                median_return_pct=pmc_summary["median_return_pct"],
                p5_return_pct=pmc_summary["p5_return_pct"],
                p95_return_pct=pmc_summary["p95_return_pct"],
                worst_drawdown_p95=pmc_summary["worst_drawdown_p95"],
                n_paths=self._config.mc_simulations,
                correlation_matrix=corr_matrix,
            )

        return RiskLevelResult(
            risk_level=risk_level.value,
            stock_results=stock_results,
            monte_carlo_projections=mc_projections,
            strategy_assessments=[],
            total_return_pct=total_return,
            avg_sharpe=avg_sharpe,
            avg_max_drawdown=avg_dd,
            total_trades=total_trades,
            portfolio_metrics=portfolio_metrics,
            portfolio_monte_carlo=portfolio_mc,
        )

    async def _fetch_bars(self, symbol: str) -> list[OHLCBar]:
        """Fetch OHLC bars via yfinance, with optional disk cache."""
        if self._bar_cache is not None:
            cached = self._bar_cache.get(symbol)
            if cached is not None:
                return cached

        from src.data.providers import yfinance_provider
        from src.data.providers.base import Interval

        # Convert trading days to calendar days (~1.5x for weekends/holidays)
        total_trading_days = self._config.train_days + self._config.test_days
        total_calendar_days = int(total_trading_days * 1.5) + 20
        since_ts = int((datetime.now(UTC) - timedelta(days=total_calendar_days)).timestamp())
        bars = await yfinance_provider.download(
            symbol,
            interval=Interval.D1,
            since=since_ts,
        )

        if self._bar_cache is not None and bars:
            self._bar_cache.put(symbol, bars)

        return bars

    def _bars_to_ticks(self, bars: list[OHLCBar], symbol: str) -> list[MarketTick]:
        """Convert OHLCBar list to MarketTick list."""
        ticks = []
        for bar in bars:
            ticks.append(
                MarketTick(
                    symbol=symbol,
                    price=Decimal(bar.close),
                    volume=int(float(bar.volume)),
                    timestamp=datetime.fromtimestamp(bar.timestamp, tz=UTC),
                    asset_type=AssetType.STOCK,
                )
            )
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
            # Use portfolio-level metrics when available, otherwise per-stock averages
            if result.portfolio_metrics is not None:
                sharpe = result.portfolio_metrics.sharpe_ratio
                ret = result.portfolio_metrics.total_return_pct
                dd = result.portfolio_metrics.max_drawdown
            else:
                sharpe = result.avg_sharpe
                ret = result.total_return_pct
                dd = result.avg_max_drawdown
            sharpe = sharpe if not math.isnan(sharpe) else 0.0
            ret = ret if not math.isnan(ret) else 0.0
            dd = dd if not math.isnan(dd) else 0.0
            scores[level] = sharpe * 0.5 + ret * 0.3 - dd * 0.2

        best_level = max(scores, key=lambda k: scores[k])
        best_score = scores[best_level]
        best_result = results[best_level]

        # Confidence: how much better is best vs average?
        avg_score = sum(scores.values()) / len(scores) if scores else 0.0
        spread = best_score - avg_score
        confidence = min(1.0, max(0.1, 0.5 + spread * 0.1))

        # Strategy weight suggestion
        weights: dict[str, float] = {}
        if best_result.stock_results:
            total_wins = sum(r.winning_trades for r in best_result.stock_results)
            if total_wins > 0:
                weights["momentum"] = 0.5
                weights["quantitative"] = 0.5

        if best_result.portfolio_metrics is not None:
            pm = best_result.portfolio_metrics
            reasoning = (
                f"'{best_level}' achieved the best risk-adjusted score ({best_score:.2f}): "
                f"portfolio return {pm.total_return_pct:.2f}%, "
                f"portfolio Sharpe {pm.sharpe_ratio:.3f}, "
                f"portfolio max drawdown {pm.max_drawdown:.2f}%."
            )
        else:
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
