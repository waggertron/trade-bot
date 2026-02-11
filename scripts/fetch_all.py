"""Orchestration script to download all historical datasets.

Usage:
    uv run python -m scripts.fetch_all
    uv run python -m scripts.fetch_all --category stocks
    uv run python -m scripts.fetch_all --category crypto --no-combine
    uv run python -m scripts.fetch_all --dry-run
    uv run python -m scripts.fetch_all --update
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass

from src.data.combiner import combine_datasets
from src.data.downloader import (
    download_from_provider,
    incremental_download,
    save_bars,
    update_catalog_for_file,
)
from src.data.providers.base import Interval, ProviderName

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class DownloadTask:
    symbol: str
    source: ProviderName
    interval: Interval
    category: str  # stocks, bonds, crypto


STOCK_SYMBOLS = [
    "SPY", "QQQ", "DIA", "IWM",
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "XLF", "XLK", "XLE", "XLV", "XLI",
]

BOND_SYMBOLS = ["TLT", "AGG", "BND", "SHY"]

CRYPTO_PAIRS = [
    "BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD", "XRP/USD",
    "ADA/USD", "DOGE/USD", "AVAX/USD", "DOT/USD", "LINK/USD",
]

# Sources for crypto daily: CryptoCompare, yfinance, Binance
CRYPTO_DAILY_SOURCES = [
    ProviderName.CRYPTOCOMPARE,
    ProviderName.YFINANCE,
    ProviderName.BINANCE,
]

# Sources for crypto hourly: CryptoCompare, Binance
CRYPTO_HOURLY_SOURCES = [
    ProviderName.CRYPTOCOMPARE,
    ProviderName.BINANCE,
]


def build_tasks() -> list[DownloadTask]:
    """Build the full list of download tasks."""
    tasks: list[DownloadTask] = []

    # Stocks — yfinance daily (16 tasks)
    for sym in STOCK_SYMBOLS:
        tasks.append(DownloadTask(
            symbol=sym, source=ProviderName.YFINANCE,
            interval=Interval.D1, category="stocks",
        ))

    # Bonds — yfinance daily (4 tasks)
    for sym in BOND_SYMBOLS:
        tasks.append(DownloadTask(
            symbol=sym, source=ProviderName.YFINANCE,
            interval=Interval.D1, category="bonds",
        ))

    # Crypto daily: 3 sources x 10 pairs = 30 tasks
    for pair in CRYPTO_PAIRS:
        for source in CRYPTO_DAILY_SOURCES:
            tasks.append(DownloadTask(
                symbol=pair, source=source,
                interval=Interval.D1, category="crypto",
            ))

    # Crypto hourly: 2 sources x 10 pairs = 20 tasks
    for pair in CRYPTO_PAIRS:
        for source in CRYPTO_HOURLY_SOURCES:
            tasks.append(DownloadTask(
                symbol=pair, source=source,
                interval=Interval.H1, category="crypto",
            ))

    return tasks


async def execute_task(task: DownloadTask, update_mode: bool = False) -> None:
    """Execute a single download task."""
    label = f"{task.symbol} {task.interval.value} from {task.source.value}"
    logger.info("Downloading %s ...", label)

    try:
        if update_mode:
            bars = await incremental_download(task.source, task.symbol, task.interval)
            logger.info("  -> %d total bars (incremental)", len(bars))
        else:
            bars = await download_from_provider(
                task.source, task.symbol, task.interval,
            )
            if not bars:
                logger.warning("  -> No data returned for %s", label)
                return
            file_path = save_bars(bars, task.symbol, task.source.value, task.interval.value)
            update_catalog_for_file(
                task.symbol, task.source.value, task.interval.value, file_path, bars,
            )
            logger.info("  -> %d bars saved", len(bars))
    except Exception:
        logger.exception("  FAILED: %s", label)


def run_combines() -> None:
    """Combine multi-source crypto datasets."""
    for pair in CRYPTO_PAIRS:
        for interval_val in ["1d", "1h"]:
            logger.info("Combining %s %s ...", pair, interval_val)
            try:
                result = combine_datasets(pair, interval_val)
                logger.info("  -> %s", result.summary().replace("\n", " | "))
            except Exception:
                logger.exception("  FAILED combining %s %s", pair, interval_val)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download all historical datasets")
    parser.add_argument(
        "--category",
        choices=["stocks", "bonds", "crypto"],
        default=None,
        help="Only download a specific category",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show tasks without executing")
    parser.add_argument("--update", action="store_true", help="Incremental update mode")
    parser.add_argument("--no-combine", action="store_true", help="Skip combining crypto datasets")
    return parser


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    all_tasks = build_tasks()

    if args.category:
        all_tasks = [t for t in all_tasks if t.category == args.category]

    print(f"Total tasks: {len(all_tasks)}")

    if args.dry_run:
        for i, t in enumerate(all_tasks, 1):
            src = t.source.value
            print(f"  [{i:>2}] {t.symbol:<10} {t.interval.value:<4} {src:<15} ({t.category})")
        if not args.no_combine:
            print(f"\nCombine steps: {len(CRYPTO_PAIRS) * 2} (10 pairs x 2 intervals)")
        return

    total = len(all_tasks)
    for i, task in enumerate(all_tasks, 1):
        print(f"[{i}/{total}] {task.symbol} {task.interval.value} from {task.source.value}")
        await execute_task(task, update_mode=args.update)

    if not args.no_combine and args.category in (None, "crypto"):
        print("\nCombining crypto datasets...")
        run_combines()

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
