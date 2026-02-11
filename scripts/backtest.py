"""CLI script to download historical data and run backtests.

Usage:
    uv run python -m scripts.backtest --symbol BTC/USD --interval 60 --days 30
    uv run python -m scripts.backtest --symbol BTC/USD --days 7 --cash 1000 --risk-level conservative
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import time
from decimal import Decimal
from pathlib import Path

from src.core.config import RISK_LEVEL_PRESETS, RiskLevel, RiskSettings
from src.data.downloader import (
    DATA_DIR,
    bars_to_ticks,
    download_ohlc,
    load_csv,
    save_to_csv,
)
from src.data.backtester import run_backtest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

RISK_LEVEL_NAMES = [r.value for r in RiskLevel]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download historical data and run backtest")
    parser.add_argument("--symbol", default="BTC/USD", help="Trading pair (default: BTC/USD)")
    parser.add_argument("--interval", type=int, default=60, help="Candle interval in minutes (default: 60)")
    parser.add_argument("--days", type=int, default=7, help="Number of days of history (default: 7)")
    parser.add_argument("--cash", type=float, default=100_000, help="Initial cash (default: 100000)")
    parser.add_argument(
        "--risk-level",
        choices=RISK_LEVEL_NAMES,
        default=None,
        help=f"Risk level preset: {', '.join(RISK_LEVEL_NAMES)} (default: moderate)",
    )
    parser.add_argument(
        "--position-size",
        type=float,
        default=None,
        help="Override position size %% of portfolio per trade (e.g., 2.0 for 2%%)",
    )
    parser.add_argument("--force-download", action="store_true", help="Re-download even if CSV exists")
    return parser.parse_args()


def build_risk_settings(args: argparse.Namespace) -> RiskSettings:
    """Build RiskSettings from CLI args."""
    if args.risk_level:
        overrides = {}
        if args.position_size is not None:
            overrides["max_position_pct"] = args.position_size
        settings = RiskSettings.from_risk_level(args.risk_level, **overrides)
    else:
        if args.position_size is not None:
            settings = RiskSettings(max_position_pct=args.position_size)
        else:
            settings = RiskSettings()  # moderate defaults

    return settings


async def main() -> None:
    args = parse_args()
    risk_settings = build_risk_settings(args)

    pair = args.symbol.replace("/", "")
    csv_path = DATA_DIR / f"{pair}_{args.interval}m.csv"

    # Download data if needed
    if args.force_download or not csv_path.exists():
        since = int(time.time()) - (args.days * 86400)
        logger.info("Downloading %d days of %s %dm data...", args.days, args.symbol, args.interval)
        bars = await download_ohlc(
            symbol=args.symbol,
            interval=args.interval,
            since=since,
        )
        if not bars:
            logger.error("No data returned from Kraken")
            return
        csv_path = save_to_csv(bars, args.symbol, args.interval)
        logger.info("Downloaded %d bars to %s", len(bars), csv_path)
    else:
        logger.info("Using cached data from %s", csv_path)

    # Load and run backtest
    bars = load_csv(csv_path)
    ticks = bars_to_ticks(bars, args.symbol)

    print(f"\nRisk level: {args.risk_level or 'moderate (default)'}")
    print(f"Position size: {risk_settings.max_position_pct}% of portfolio per trade")
    print(f"Max open positions: {risk_settings.max_open_positions}")
    print(f"Daily loss limit: {risk_settings.daily_loss_limit_pct}%")
    logger.info("Running backtest with %d ticks...", len(ticks))

    result = await run_backtest(
        ticks,
        initial_cash=Decimal(str(args.cash)),
        risk_settings=risk_settings,
    )

    # Print trade log
    if result.fills:
        print("\n" + "=" * 60)
        print("TRADE LOG")
        print("=" * 60)
        for i, f in enumerate(result.fills, 1):
            print(f"  {i:3d}. {f.timestamp:%Y-%m-%d %H:%M} | {f.side.value.upper():4s} | "
                  f"qty={f.quantity} | price=${f.fill_price:,.2f}")
    else:
        print("\nNo trades executed during backtest period.")

    # Print summary
    print("\n" + result.summary())


if __name__ == "__main__":
    asyncio.run(main())
