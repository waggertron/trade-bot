"""Sentiment-aware backtest comparison script.

Runs 4 backtests side-by-side for a window determined by available sentiment data:
  1. Baseline     — Momentum + Quantitative only
  2. Sentiment    — same + SentimentStrategy, fed by lookahead-free historical scores
  3. SPY B&H      — passive buy-and-hold benchmark
  4. SPY DCA      — SPY daily cost-averaging benchmark

Usage:
    uv run python scripts/compare_sentiment_backtest.py \
        --symbols AAPL MSFT NVDA TSLA SPY \
        --days 30 \
        --cash 10000 \
        --buy-threshold 0.1 \
        --sell-threshold -0.1
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Ensure project root is importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.strategies.sentiment import SentimentStrategy
from src.core.models import AssetType, MarketTick
from src.data.backtester import BacktestResult, run_backtest
from src.data.providers.base import Interval, OHLCBar
from src.data.providers.yfinance_provider import download
from src.db.database import Database
from src.simulation.benchmark import BenchmarkSimulator
from src.simulation.sentiment_backtest import SentimentBacktestLoader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bars_to_ticks(bars: list[OHLCBar], symbol: str) -> list[MarketTick]:
    ticks = []
    for bar in bars:
        ticks.append(MarketTick(
            symbol=symbol,
            price=Decimal(bar.close),
            volume=int(float(bar.volume or "0")),
            timestamp=datetime.fromtimestamp(bar.timestamp, tz=timezone.utc),
            asset_type=AssetType.CRYPTO if "/" in symbol else AssetType.STOCK,
        ))
    return ticks


def _filter_bars(bars: list[OHLCBar], start_ts: int, end_ts: int) -> list[OHLCBar]:
    return [b for b in bars if start_ts <= b.timestamp <= end_ts]


def _print_coverage(loader: SentimentBacktestLoader, window_start: datetime, window_end: datetime) -> None:
    cov = loader.coverage
    print()
    print("=== SENTIMENT COVERAGE REPORT ===")
    print(f"  Symbols:      {' '.join(cov['symbols'])}")
    print(f"  Articles:     {cov['total_articles']:,}")
    if cov["min_date"] and cov["max_date"]:
        min_d = cov["min_date"].strftime("%Y-%m-%d")
        max_d = cov["max_date"].strftime("%Y-%m-%d")
        print(f"  Date range:   {min_d} → {max_d}")
        articles_per_day = cov.get("articles_per_day", {})
        if articles_per_day:
            avg_per_day = len(articles_per_day) and cov["total_articles"] / len(articles_per_day)
            print(f"  Avg/day:      {avg_per_day:.0f} articles/day")
    print(f"  Backtest:     {window_end - window_start} ending {window_end.strftime('%Y-%m-%d')}")
    print()


def _format_result(result: BacktestResult) -> tuple[str, str, str, str, str]:
    """Return (return%, max_dd, sharpe, trades, win_rate) as formatted strings."""
    return (
        f"{result.return_pct:+.2f}%",
        f"{result.max_drawdown:.2f}%",
        f"{result.sharpe_ratio:.3f}",
        str(result.total_trades),
        f"{result.win_rate:.1%}",
    )


def _run_spy_benchmarks(
    bars: list[OHLCBar], cash: float,
) -> tuple:
    """Return (buy_and_hold, dca) BenchmarkResult pair for the given bars."""
    sim = BenchmarkSimulator()
    return sim.buy_and_hold(bars, cash), sim.monthly_dca(bars, cash)


def _count_sentiment_signals(result: BacktestResult) -> tuple[int, int]:
    """Count buy/sell fills from the sentiment strategy (rough proxy via fill count)."""
    buys = sum(1 for f in result.fills if f.side.value == "buy")
    sells = sum(1 for f in result.fills if f.side.value == "sell")
    return buys, sells


# ---------------------------------------------------------------------------
# Main async logic
# ---------------------------------------------------------------------------

async def main(
    symbols: list[str],
    days: int,
    cash: float,
    buy_threshold: float,
    sell_threshold: float,
    db_path: str,
) -> None:
    db_url = f"sqlite+aiosqlite:///{db_path}"
    db = Database(db_url)
    await db.initialize()

    try:
        # -- Load sentiment data --------------------------------------------------
        loader = SentimentBacktestLoader(db, symbols)
        await loader.load()

        cov = loader.coverage
        if cov["max_date"] is None:
            print("No scored articles found in the database. Run the sentiment pipeline first.")
            return

        window_end: datetime = cov["max_date"]
        window_start: datetime = window_end - timedelta(days=days)
        _print_coverage(loader, window_start, window_end)

        start_ts = int(window_start.timestamp())
        end_ts = int(window_end.timestamp())

        # -- Download bars -------------------------------------------------------
        print("Downloading OHLC bars via yfinance …")
        all_bars: dict[str, list[OHLCBar]] = {}
        for sym in symbols:
            bars = await download(sym, interval=Interval.D1, since=start_ts)
            all_bars[sym] = _filter_bars(bars, start_ts, end_ts)
            print(f"  {sym}: {len(all_bars[sym])} bars")

        spy_bars = all_bars.get("SPY", [])

        # -- Run backtests per symbol -------------------------------------------
        print()
        print("=== PER-SYMBOL RESULTS ===")
        header = f"{'Symbol':<8} | {'No-Sent %':>10} | {'Sent %':>10} | {'SPY B&H %':>10} | {'SPY DCA %':>10} | Sentiment Signals"
        print(header)
        print("-" * len(header))

        agg_no_sent: list[BacktestResult] = []
        agg_with_sent: list[BacktestResult] = []
        agg_spy_bh_returns: list[float] = []
        agg_spy_dca_returns: list[float] = []

        initial_cash = Decimal(str(cash))
        sentiment_strategy = SentimentStrategy(
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
        )

        for sym in symbols:
            bars = all_bars[sym]
            if not bars:
                print(f"{sym:<8} | {'N/A':>10} | {'N/A':>10} | {'N/A':>10} | {'N/A':>10} | no bar data")
                continue

            ticks = _bars_to_ticks(bars, sym)

            # 1. Baseline
            result_base = await run_backtest(ticks, initial_cash=initial_cash)

            # 2. With sentiment
            result_sent = await run_backtest(
                ticks,
                initial_cash=initial_cash,
                extra_strategies=[sentiment_strategy],
                research_at=loader.get_research_at,
            )

            # 3 & 4. SPY buy-and-hold + DCA (use SPY bars, or same bars when sym == SPY)
            bh_bars = bars if sym == "SPY" else spy_bars
            if bh_bars:
                bh, dca = _run_spy_benchmarks(bh_bars, cash)
                bh_ret_str = f"{bh.return_pct:+.2f}%"
                dca_ret_str = f"{dca.return_pct:+.2f}%"
                agg_spy_bh_returns.append(bh.return_pct)
                agg_spy_dca_returns.append(dca.return_pct)
            else:
                bh_ret_str = "N/A"
                dca_ret_str = "N/A"

            buys, sells = _count_sentiment_signals(result_sent)

            print(
                f"{sym:<8} | {result_base.return_pct:>+10.2f}% | "
                f"{result_sent.return_pct:>+10.2f}% | "
                f"{bh_ret_str:>10} | "
                f"{dca_ret_str:>10} | "
                f"{buys} buys, {sells} sells"
            )

            agg_no_sent.append(result_base)
            agg_with_sent.append(result_sent)

        # -- Aggregated comparison ---------------------------------------------
        if not agg_no_sent:
            return

        def _avg(vals: list[float]) -> float:
            return sum(vals) / len(vals) if vals else 0.0

        avg_ret_base = _avg([r.return_pct for r in agg_no_sent])
        avg_ret_sent = _avg([r.return_pct for r in agg_with_sent])
        avg_ret_spy_bh = _avg(agg_spy_bh_returns)
        avg_ret_spy_dca = _avg(agg_spy_dca_returns)

        avg_dd_base = _avg([r.max_drawdown for r in agg_no_sent])
        avg_dd_sent = _avg([r.max_drawdown for r in agg_with_sent])

        avg_sharpe_base = _avg([r.sharpe_ratio for r in agg_no_sent])
        avg_sharpe_sent = _avg([r.sharpe_ratio for r in agg_with_sent])

        total_trades_base = sum(r.total_trades for r in agg_no_sent)
        total_trades_sent = sum(r.total_trades for r in agg_with_sent)

        win_rates_base = [r.win_rate for r in agg_no_sent if (r.winning_trades + r.losing_trades) > 0]
        win_rates_sent = [r.win_rate for r in agg_with_sent if (r.winning_trades + r.losing_trades) > 0]
        avg_wr_base = _avg(win_rates_base)
        avg_wr_sent = _avg(win_rates_sent)

        col_w = 16
        print()
        print("=== AGGREGATED COMPARISON ===")
        print(f"{'Metric':<16} | {'No Sentiment':>{col_w}} | {'With Sentiment':>{col_w}} | {'SPY Buy-and-Hold':>{col_w}} | {'SPY DCA':>{col_w}}")
        print("-" * (16 + col_w * 4 + 13))
        print(f"{'Return %':<16} | {avg_ret_base:>{col_w}.2f}% | {avg_ret_sent:>{col_w}.2f}% | {avg_ret_spy_bh:>{col_w}.2f}% | {avg_ret_spy_dca:>{col_w}.2f}%")
        print(f"{'Max Drawdown':<16} | {avg_dd_base:>{col_w}.2f}% | {avg_dd_sent:>{col_w}.2f}% | {'N/A':>{col_w}} | {'N/A':>{col_w}}")
        print(f"{'Sharpe Ratio':<16} | {avg_sharpe_base:>{col_w}.3f} | {avg_sharpe_sent:>{col_w}.3f} | {'N/A':>{col_w}} | {'N/A':>{col_w}}")
        print(f"{'Total Trades':<16} | {total_trades_base:>{col_w}} | {total_trades_sent:>{col_w}} | {'N/A':>{col_w}} | {'N/A':>{col_w}}")
        print(f"{'Win Rate':<16} | {avg_wr_base:>{col_w}.1%} | {avg_wr_sent:>{col_w}.1%} | {'N/A':>{col_w}} | {'N/A':>{col_w}}")

        sharpe_delta = avg_sharpe_sent - avg_sharpe_base
        ret_delta = avg_ret_sent - avg_ret_base
        sign = "+" if sharpe_delta >= 0 else ""
        rsign = "+" if ret_delta >= 0 else ""
        print()
        print(
            f"Sentiment delta: {sign}{sharpe_delta:.3f} Sharpe, "
            f"{rsign}{ret_delta:.2f}% return vs baseline."
        )

    finally:
        await db.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def cli() -> None:
    parser = argparse.ArgumentParser(
        description="Run sentiment-aware backtest comparison",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--symbols", nargs="+", default=["AAPL", "MSFT", "NVDA", "TSLA", "SPY"],
        help="Symbols to backtest",
    )
    parser.add_argument("--days", type=int, default=30, help="Backtest window in calendar days")
    parser.add_argument("--cash", type=float, default=10000.0, help="Initial cash per symbol")
    parser.add_argument("--buy-threshold", type=float, default=0.1, help="Sentiment buy threshold")
    parser.add_argument("--sell-threshold", type=float, default=-0.1, help="Sentiment sell threshold")
    parser.add_argument(
        "--db-path", default="trade_bot.db",
        help="Path to SQLite database file",
    )
    args = parser.parse_args()

    asyncio.run(main(
        symbols=args.symbols,
        days=args.days,
        cash=args.cash,
        buy_threshold=args.buy_threshold,
        sell_threshold=args.sell_threshold,
        db_path=args.db_path,
    ))


if __name__ == "__main__":
    cli()
