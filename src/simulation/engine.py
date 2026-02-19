"""Simulation engine: orchestrates data fetch, backtest, MC projection, and assessment."""
from __future__ import annotations

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
                # Adapt SMA windows to fit available test data
                n_ticks = len(ticks)
                long_window = min(20, n_ticks // 2) if n_ticks < 50 else 50
                short_window = max(3, long_window // 3)
                # Lower z-threshold so quant strategy fires on daily data
                quant_z = 1.0 if n_ticks < 100 else 2.0
                bt_result = await run_backtest(
                    ticks,
                    initial_cash=Decimal(str(self._config.initial_balance)),
                    short_window=short_window,
                    long_window=long_window,
                    quant_z_threshold=quant_z,
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
            strategy_assessments=[],
            total_return_pct=total_return,
            avg_sharpe=avg_sharpe,
            avg_max_drawdown=avg_dd,
            total_trades=total_trades,
        )

    async def _fetch_bars(self, symbol: str) -> list[OHLCBar]:
        """Fetch OHLC bars via yfinance."""
        from src.data.providers import yfinance_provider
        from src.data.providers.base import Interval

        # Convert trading days to calendar days (~1.5x for weekends/holidays)
        total_trading_days = self._config.train_days + self._config.test_days
        total_calendar_days = int(total_trading_days * 1.5) + 20
        since_ts = int((datetime.now(UTC) - timedelta(days=total_calendar_days)).timestamp())
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

        # Strategy weight suggestion
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
