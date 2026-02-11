"""Regime tagging: label fills with volatility regimes and compute per-regime stats."""

from __future__ import annotations

from collections import defaultdict

from src.analytics.models import AttributedFill, StrategyStats, Trade
from src.core.models import Fill, OrderSide


class RegimeTagger:
    """Tag fills with market-regime labels and compute per-regime performance."""

    def __init__(self) -> None:
        self._regimes: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Regime storage
    # ------------------------------------------------------------------

    def set_regime(self, symbol: str, timestamp: int, regime: str) -> None:
        """Store a regime label for a symbol at a given unix timestamp."""
        key = f"{symbol}:{timestamp}"
        self._regimes[key] = regime

    def get_regime(self, symbol: str, timestamp: int) -> str:
        """Return the regime for a symbol/timestamp, or ``'unknown'`` if not set."""
        key = f"{symbol}:{timestamp}"
        return self._regimes.get(key, "unknown")

    # ------------------------------------------------------------------
    # Fill tagging
    # ------------------------------------------------------------------

    def tag_fills(
        self,
        fills: list[Fill],
        strategy_map: dict[str, str] | None = None,
    ) -> list[AttributedFill]:
        """Create :class:`AttributedFill` entries from raw fills.

        Parameters
        ----------
        fills:
            Raw fills to tag.
        strategy_map:
            Optional mapping of ``fill.id`` to strategy name.
        """
        result: list[AttributedFill] = []
        for fill in fills:
            regime = self.get_regime(fill.symbol, int(fill.timestamp.timestamp()))
            strategy = strategy_map.get(fill.id, "") if strategy_map else ""
            result.append(
                AttributedFill(fill=fill, strategy=strategy, regime=regime),
            )
        return result

    # ------------------------------------------------------------------
    # Per-regime performance
    # ------------------------------------------------------------------

    def performance_by_regime(
        self,
        fills: list[AttributedFill],
    ) -> dict[str, StrategyStats]:
        """Group attributed fills by regime and compute :class:`StrategyStats` for each."""
        if not fills:
            return {}

        by_regime: dict[str, list[AttributedFill]] = defaultdict(list)
        for af in fills:
            by_regime[af.regime].append(af)

        stats: dict[str, StrategyStats] = {}
        for regime_name, regime_fills in by_regime.items():
            trades = _pair_fills(regime_fills)
            stats[regime_name] = _compute_stats(regime_name, trades)

        return stats


# ------------------------------------------------------------------
# FIFO pairing (inline to avoid circular dependency with attribution)
# ------------------------------------------------------------------


def _pair_fills(fills: list[AttributedFill]) -> list[Trade]:
    """FIFO pairing: for each symbol, match buy fills with sell fills in order."""
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
                ),
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
    """Compute :class:`StrategyStats` from a list of paired trades."""
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
