"""Strategy attribution: FIFO fill pairing and per-strategy performance stats."""

from __future__ import annotations

from collections import defaultdict

from src.analytics.models import AttributedFill, AttributionReport, StrategyStats, Trade
from src.core.models import OrderSide


class StrategyAttribution:
    """Attribute fills to strategies, pair them into trades, and compute stats."""

    def analyze(self, fills: list[AttributedFill]) -> AttributionReport:
        """Group fills by strategy, pair into trades, and return an AttributionReport."""
        if not fills:
            return AttributionReport(
                strategies={},
                total_pnl=0.0,
                best_strategy="",
                worst_strategy="",
            )

        # Group fills by strategy
        by_strategy: dict[str, list[AttributedFill]] = defaultdict(list)
        for af in fills:
            by_strategy[af.strategy].append(af)

        # Compute per-strategy stats
        strategies: dict[str, StrategyStats] = {}
        for strategy_name, strategy_fills in by_strategy.items():
            trades = _pair_fills(strategy_fills)
            strategies[strategy_name] = _compute_stats(strategy_name, trades)

        # Compute overall metrics
        total_pnl = sum(s.total_pnl for s in strategies.values())

        # Determine best/worst only among strategies that have trades
        strategies_with_trades = {
            name: stats for name, stats in strategies.items() if stats.total_trades > 0
        }

        if strategies_with_trades:
            best_strategy = max(
                strategies_with_trades,
                key=lambda n: strategies_with_trades[n].total_pnl,
            )
            worst_strategy = min(
                strategies_with_trades,
                key=lambda n: strategies_with_trades[n].total_pnl,
            )
        else:
            best_strategy = ""
            worst_strategy = ""

        return AttributionReport(
            strategies=strategies,
            total_pnl=total_pnl,
            best_strategy=best_strategy,
            worst_strategy=worst_strategy,
        )


def _pair_fills(fills: list[AttributedFill]) -> list[Trade]:
    """FIFO pairing: for each symbol, match buy fills with sell fills in order."""
    # Separate buys and sells per symbol
    buys: dict[str, list[AttributedFill]] = defaultdict(list)
    sells: dict[str, list[AttributedFill]] = defaultdict(list)

    for af in fills:
        if af.fill.side == OrderSide.BUY:
            buys[af.fill.symbol].append(af)
        else:
            sells[af.fill.symbol].append(af)

    trades: list[Trade] = []

    for symbol in buys:
        buy_queue = list(buys[symbol])  # FIFO order
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


def _max_losing_streak(trades: list[Trade]) -> int:
    """Count the maximum consecutive trades where pnl <= 0."""
    if not trades:
        return 0

    max_streak = 0
    current_streak = 0

    for trade in trades:
        if trade.pnl <= 0:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    return max_streak


def _compute_stats(name: str, trades: list[Trade]) -> StrategyStats:
    """Compute StrategyStats from a list of trades."""
    if not trades:
        return StrategyStats(name=name)

    total_trades = len(trades)
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]

    win_rate = len(wins) / total_trades if total_trades else 0.0
    total_pnl = sum(t.pnl for t in trades)
    avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0.0

    loss_total = sum(t.pnl for t in losses)
    if losses and loss_total != 0:
        profit_factor = sum(t.pnl for t in wins) / abs(loss_total)
    else:
        profit_factor = 0.0

    max_consecutive_losses = _max_losing_streak(trades)

    return StrategyStats(
        name=name,
        total_trades=total_trades,
        win_rate=win_rate,
        total_pnl=total_pnl,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor,
        max_consecutive_losses=max_consecutive_losses,
    )
