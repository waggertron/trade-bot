"""AnalyticsReporter: generate formatted multi-section text reports."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from src.analytics.models import AttributedFill, AttributionReport, MonteCarloResult, Trade
from src.core.models import OrderSide

if TYPE_CHECKING:
    from src.analytics.attribution import StrategyAttribution
    from src.analytics.monte_carlo import MonteCarloSimulator


class AnalyticsReporter:
    """Combine attribution analysis and Monte Carlo simulation into a text report."""

    def __init__(
        self,
        attribution: StrategyAttribution,
        simulator: MonteCarloSimulator,
    ) -> None:
        self._attribution = attribution
        self._simulator = simulator

    def generate_report(self, fills: list[AttributedFill], initial_cash: float) -> str:
        """Run attribution + Monte Carlo and return a formatted multi-section report."""
        # 1. Attribution analysis
        attr_report: AttributionReport = self._attribution.analyze(fills)

        # 2. Pair fills into trades for Monte Carlo
        trades = _pair_fills_into_trades(fills)

        # 3. Monte Carlo simulation
        mc_result: MonteCarloResult = self._simulator.simulate(trades, initial_cash)

        # 4. Compute top-level return percentage
        total_pnl = attr_report.total_pnl
        return_pct = (total_pnl / initial_cash * 100.0) if initial_cash else 0.0
        trade_count = sum(s.total_trades for s in attr_report.strategies.values())

        # 5. Build the report
        lines: list[str] = []

        # --- Header ---
        lines.append("=" * 50)
        lines.append("ANALYTICS REPORT")
        lines.append("=" * 50)
        lines.append(f"Total P&L:        ${total_pnl:,.2f}")
        lines.append(f"Return:           {return_pct:.2f}%")
        lines.append(f"Total Trades:     {trade_count}")

        # --- Strategy breakdown ---
        lines.append("-" * 50)
        lines.append("STRATEGY BREAKDOWN")
        lines.append("-" * 50)

        for name in sorted(attr_report.strategies):
            stats = attr_report.strategies[name]
            lines.append(f"{name}:")
            lines.append(f"  Trades: {stats.total_trades}  Win Rate: {stats.win_rate:.1%}")
            lines.append(
                f"  P&L: ${stats.total_pnl:,.2f}  Profit Factor: {stats.profit_factor:.2f}"
            )
            lines.append(f"  Avg Win: ${stats.avg_win:,.2f}  Avg Loss: ${stats.avg_loss:,.2f}")
            lines.append(f"  Max Consecutive Losses: {stats.max_consecutive_losses}")

        # --- Monte Carlo ---
        lines.append("-" * 50)
        lines.append(f"MONTE CARLO ANALYSIS ({mc_result.n_simulations} simulations)")
        lines.append("-" * 50)
        lines.append(f"Actual Final:     ${mc_result.actual_final_value:,.2f}")
        lines.append(f"Percentile:       {mc_result.percentile:.1f}%")
        lines.append(f"Median Simulated: ${mc_result.median_simulated:,.2f}")
        lines.append(
            f"95% CI:           ${mc_result.p5_simulated:,.2f} - ${mc_result.p95_simulated:,.2f}"
        )
        lines.append(f"Worst Drawdown (95%): {mc_result.worst_drawdown_p95:.1%}")
        lines.append("=" * 50)

        return "\n".join(lines)


def _pair_fills_into_trades(fills: list[AttributedFill]) -> list[Trade]:
    """FIFO pairing of all fills (across all strategies) into Trade objects."""
    buys: dict[str, list[AttributedFill]] = defaultdict(list)
    sells: dict[str, list[AttributedFill]] = defaultdict(list)

    for af in fills:
        if af.fill.side == OrderSide.BUY:
            buys[af.fill.symbol].append(af)
        else:
            sells[af.fill.symbol].append(af)

    trades: list[Trade] = []

    for symbol in buys:
        buy_queue = list(buys[symbol])
        sell_queue = list(sells.get(symbol, []))

        buy_idx = 0
        sell_idx = 0

        while buy_idx < len(buy_queue) and sell_idx < len(sell_queue):
            buy_fill = buy_queue[buy_idx]
            sell_fill = sell_queue[sell_idx]

            entry_price = float(buy_fill.fill.fill_price)
            exit_price = float(sell_fill.fill.fill_price)
            quantity = float(min(buy_fill.fill.quantity, sell_fill.fill.quantity))
            pnl = (exit_price - entry_price) * quantity

            trades.append(
                Trade(
                    symbol=symbol,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    quantity=quantity,
                    pnl=pnl,
                    strategy=buy_fill.strategy,
                    regime=buy_fill.regime,
                )
            )

            buy_idx += 1
            sell_idx += 1

    return trades
