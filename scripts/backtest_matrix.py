"""Run backtests across multiple timeframes and risk levels, output results table.

Usage:
    uv run python -m scripts.backtest_matrix
"""
from __future__ import annotations

import asyncio
import csv as csv_mod
import logging
import time
from decimal import Decimal

from src.core.config import RiskLevel, RiskSettings
from src.data.backtester import run_backtest
from src.data.downloader import DATA_DIR, bars_to_ticks, download_ohlc, load_csv

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SYMBOL = "BTC/USD"
# Use 4h candles — Kraken serves max ~720 bars per page, so 4h gives us
# ~120 days per page.  With pagination we can fetch 240+ days.
INTERVAL = 240
INITIAL_CASH = Decimal("1000")
DAYS_LIST = [30, 60, 90, 120, 150, 180, 210, 240]
RISK_LEVELS = [
    RiskLevel.CONSERVATIVE,
    RiskLevel.MODERATE,
    RiskLevel.AGGRESSIVE,
    RiskLevel.VERY_AGGRESSIVE,
]


async def download_data(max_days: int):
    """Download OHLC data covering at least max_days, return path."""
    pair = SYMBOL.replace("/", "")
    csv_path = DATA_DIR / f"{pair}_{INTERVAL}m_{max_days}d.csv"

    if csv_path.exists():
        logger.info("Using cached data from %s", csv_path)
        return csv_path

    since = int(time.time()) - (max_days * 86400)
    logger.info("Downloading %d days of %s %dm data...", max_days, SYMBOL, INTERVAL)
    bars = await download_ohlc(symbol=SYMBOL, interval=INTERVAL, since=since)
    if not bars:
        logger.error("No data returned from Kraken")
        return None

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        writer = csv_mod.DictWriter(
            f, fieldnames=["timestamp", "open", "high", "low", "close", "volume"]
        )
        writer.writeheader()
        writer.writerows(bars)
    logger.info("Downloaded %d bars to %s", len(bars), csv_path)
    return csv_path


async def main() -> None:
    max_days = max(DAYS_LIST)
    csv_path = await download_data(max_days)
    if csv_path is None:
        return

    all_bars = load_csv(csv_path)
    all_ticks = bars_to_ticks(all_bars, SYMBOL)
    total_days_available = len(all_ticks) * INTERVAL / 60 / 24
    logger.info(
        "Loaded %d ticks (%.0f days of %dm candles)", len(all_ticks), total_days_available, INTERVAL
    )

    rows = []
    total_runs = len(DAYS_LIST) * len(RISK_LEVELS)
    run_num = 0

    for days in DAYS_LIST:
        # Each tick = INTERVAL minutes, so bars_needed = days * 24h * 60min / INTERVAL
        bars_needed = days * 24 * 60 // INTERVAL
        if len(all_ticks) < bars_needed:
            ticks = all_ticks
            actual_days = len(all_ticks) * INTERVAL / 60 / 24
        else:
            ticks = all_ticks[-bars_needed:]
            actual_days = days

        for level in RISK_LEVELS:
            run_num += 1
            settings = RiskSettings.from_risk_level(level)
            logger.info(
                "[%d/%d] %dd %s (pos=%.1f%%, %d ticks, ~%.0fd actual)...",
                run_num, total_runs, days, level.value,
                settings.max_position_pct, len(ticks), actual_days,
            )
            result = await run_backtest(
                ticks,
                initial_cash=INITIAL_CASH,
                risk_settings=settings,
            )
            rows.append({
                "days": days,
                "ticks": len(ticks),
                "risk_level": level.value,
                "position_pct": settings.max_position_pct,
                "start_value": float(INITIAL_CASH),
                "end_value": result.final_value,
                "pnl": result.total_pnl,
                "return_pct": result.return_pct,
                "trades": result.total_trades,
                "win_rate": result.win_rate,
                "max_drawdown": result.max_drawdown,
                "sharpe": result.sharpe_ratio,
            })

    # Print results table
    print()
    print("=" * 130)
    print(f"BACKTEST MATRIX — {SYMBOL} — ${float(INITIAL_CASH):,.0f} starting balance — {INTERVAL}m candles")
    print("=" * 130)
    header = (
        f"{'Days':>5} | {'Ticks':>5} | {'Risk Level':<17} | {'Pos %':>5} | "
        f"{'Start':>10} | {'End':>10} | {'P&L':>10} | {'Return':>8} | "
        f"{'Trades':>6} | {'Win %':>6} | {'Max DD':>7} | {'Sharpe':>7}"
    )
    print(header)
    print("-" * 130)

    prev_days = None
    for r in rows:
        if prev_days is not None and r["days"] != prev_days:
            print("-" * 130)
        prev_days = r["days"]
        print(
            f"{r['days']:>5} | {r['ticks']:>5} | {r['risk_level']:<17} | {r['position_pct']:>4.1f}% | "
            f"${r['start_value']:>9,.2f} | ${r['end_value']:>9,.2f} | "
            f"${r['pnl']:>9,.2f} | {r['return_pct']:>7.2f}% | "
            f"{r['trades']:>6} | {r['win_rate']:>5.1%} | {r['max_drawdown']:>6.2f}% | {r['sharpe']:>7.3f}"
        )

    print("=" * 130)

    # Summary
    if rows:
        best = max(rows, key=lambda r: r["return_pct"])
        worst = min(rows, key=lambda r: r["return_pct"])
        best_sharpe = max(rows, key=lambda r: r["sharpe"])
        print(
            f"\nBest return:  {best['days']}d {best['risk_level']:<17} "
            f"return {best['return_pct']:+.2f}%, Sharpe {best['sharpe']:.3f}"
        )
        print(
            f"Worst return: {worst['days']}d {worst['risk_level']:<17} "
            f"return {worst['return_pct']:+.2f}%, Sharpe {worst['sharpe']:.3f}"
        )
        print(
            f"Best Sharpe:  {best_sharpe['days']}d {best_sharpe['risk_level']:<17} "
            f"Sharpe {best_sharpe['sharpe']:.3f}, return {best_sharpe['return_pct']:+.2f}%"
        )


if __name__ == "__main__":
    asyncio.run(main())
