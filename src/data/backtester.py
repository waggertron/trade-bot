from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from src.agents.execution import PaperExecutionAgent
from src.agents.portfolio import PortfolioManager
from src.agents.risk_manager import RiskManager
from src.agents.strategies.momentum import MomentumStrategy
from src.agents.strategies.quantitative import QuantitativeStrategy
from src.core.config import RiskSettings
from src.core.event_bus import EventBus
from src.core.models import Fill, OrderSide
from src.core.orchestrator import Orchestrator
from src.data.downloader import bars_to_ticks, load_csv

if TYPE_CHECKING:
    from pathlib import Path

    from src.core.models import MarketTick

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    total_ticks: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    initial_cash: float = 0.0
    final_value: float = 0.0
    fills: list[Fill] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        total = self.winning_trades + self.losing_trades
        if total == 0:
            return 0.0
        return self.winning_trades / total

    @property
    def return_pct(self) -> float:
        if self.initial_cash == 0:
            return 0.0
        return (self.final_value - self.initial_cash) / self.initial_cash * 100

    def summary(self) -> str:
        lines = [
            "=" * 50,
            "BACKTEST RESULTS",
            "=" * 50,
            f"Ticks processed:  {self.total_ticks}",
            f"Total trades:     {self.total_trades}",
            f"Winning trades:   {self.winning_trades}",
            f"Losing trades:    {self.losing_trades}",
            f"Win rate:         {self.win_rate:.1%}",
            "-" * 50,
            f"Initial cash:     ${self.initial_cash:,.2f}",
            f"Final value:      ${self.final_value:,.2f}",
            f"Total P&L:        ${self.total_pnl:,.2f}",
            f"Return:           {self.return_pct:,.2f}%",
            f"Max drawdown:     {self.max_drawdown:.2f}%",
            f"Sharpe ratio:     {self.sharpe_ratio:.3f}",
            "=" * 50,
        ]
        return "\n".join(lines)


def _compute_metrics(
    equity_curve: list[float],
    fills: list[Fill],
    initial_cash: float,
) -> BacktestResult:
    """Compute performance metrics from equity curve and fills."""
    result = BacktestResult(
        initial_cash=initial_cash,
        fills=fills,
        equity_curve=equity_curve,
    )

    if not equity_curve:
        return result

    result.final_value = equity_curve[-1]
    result.total_pnl = result.final_value - initial_cash

    # Pair up buy/sell fills to determine wins and losses
    open_positions: dict[str, list[Fill]] = {}
    for f in fills:
        result.total_trades += 1
        if f.side.value == "buy":
            open_positions.setdefault(f.symbol, []).append(f)
        elif f.side.value == "sell":
            buys = open_positions.get(f.symbol, [])
            if buys:
                buy_fill = buys.pop(0)
                pnl = (f.fill_price - buy_fill.fill_price) * f.quantity
                if pnl > 0:
                    result.winning_trades += 1
                else:
                    result.losing_trades += 1

    # Max drawdown
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    result.max_drawdown = max_dd

    # Sharpe-like ratio (using equity curve returns)
    if len(equity_curve) > 1:
        returns = [
            (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            for i in range(1, len(equity_curve))
            if equity_curve[i - 1] > 0
        ]
        if returns:
            mean_ret = sum(returns) / len(returns)
            variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
            std_ret = math.sqrt(variance) if variance > 0 else 0.0
            result.sharpe_ratio = (mean_ret / std_ret) if std_ret > 0 else 0.0

    return result


async def run_backtest(
    ticks: list[MarketTick],
    initial_cash: Decimal = Decimal("100000"),
    short_window: int = 14,
    long_window: int = 50,
    quant_z_threshold: float = 2.0,
    risk_settings: RiskSettings | None = None,
) -> BacktestResult:
    """Run a backtest replaying ticks through the orchestrator.

    Uses MomentumStrategy and QuantitativeStrategy (sentiment is skipped
    because there's no historical research data).
    """
    if risk_settings is None:
        risk_settings = RiskSettings()

    portfolio = PortfolioManager(initial_cash=initial_cash)
    executor = PaperExecutionAgent(slippage_pct=Decimal("0.05"))
    risk_manager = RiskManager(risk_settings)
    event_bus = EventBus()

    strategies = [
        MomentumStrategy(short_window=short_window, long_window=long_window),
        QuantitativeStrategy(z_threshold=quant_z_threshold),
    ]

    orchestrator = Orchestrator(
        strategies=strategies,
        risk_manager=risk_manager,
        executor=executor,
        portfolio=portfolio,
        event_bus=event_bus,
        position_size_pct=risk_settings.max_position_pct,
    )

    all_fills: list[Fill] = []
    equity_curve: list[float] = []

    for _i, tick in enumerate(ticks):
        # Update the executor's price so fills are realistic
        executor.set_current_price(tick.symbol, tick.price)
        # Update portfolio's current price for unrealized P&L
        portfolio.update_price(tick.symbol, tick.price)

        fills = await orchestrator.process_tick(tick)
        all_fills.extend(fills)

        # Record equity at each tick
        snapshot = await portfolio.get_snapshot()
        equity_curve.append(float(snapshot.total_value))

        if fills:
            for f in fills:
                logger.info(
                    "Trade #%d @ %s: %s %s qty=%s price=%s",
                    len(all_fills), tick.timestamp, f.side.value.upper(),
                    f.symbol, f.quantity, f.fill_price,
                )

    # Close out all remaining positions at the last tick price (standard practice)
    snapshot = await portfolio.get_snapshot()
    if snapshot.positions:
        last_tick = ticks[-1]
        for pos in snapshot.positions:
            close_fill = Fill(
                order_id="backtest-closeout",
                symbol=pos.symbol,
                side=OrderSide.SELL,
                quantity=pos.quantity,
                fill_price=pos.current_price,
                timestamp=last_tick.timestamp,
                commission=Decimal("0"),
            )
            await portfolio.record_fill(close_fill)
            all_fills.append(close_fill)

        # Update final equity after close-out
        snapshot = await portfolio.get_snapshot()
        equity_curve.append(float(snapshot.total_value))

    result = _compute_metrics(equity_curve, all_fills, float(initial_cash))
    result.total_ticks = len(ticks)
    return result


async def backtest_from_csv(
    filepath: Path,
    symbol: str,
    initial_cash: Decimal = Decimal("100000"),
    risk_settings: RiskSettings | None = None,
) -> BacktestResult:
    """Load CSV and run backtest."""
    bars = load_csv(filepath)
    ticks = bars_to_ticks(bars, symbol)
    return await run_backtest(ticks, initial_cash=initial_cash, risk_settings=risk_settings)
