"""CLI for multi-source historical data management.

Usage:
    uv run python -m scripts.data download --source cryptocompare --symbol BTC/USD --interval 1d
    uv run python -m scripts.data list
    uv run python -m scripts.data combine --symbol BTC/USD --interval 1d
    uv run python -m scripts.data update
    uv run python -m scripts.data validate --symbol BTC/USD --interval 1d
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from src.data.catalog import load_catalog
from src.data.combiner import combine_datasets, validate_dataset
from src.data.db_loader import load_all_from_catalog
from src.data.downloader import (
    download_from_provider,
    incremental_download,
    load_csv,
    save_bars,
    update_catalog_for_file,
)
from src.data.providers import PROVIDER_INTERVALS
from src.data.providers.base import Interval, ProviderName, normalize_symbol
from src.db.database import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Multi-source historical data management",
    )
    sub = parser.add_subparsers(dest="command")

    # download
    dl = sub.add_parser("download", help="Download data from a provider")
    dl.add_argument("--source", required=True, choices=[p.value for p in ProviderName])
    dl.add_argument("--symbol", required=True, help="Trading pair e.g. BTC/USD")
    dl.add_argument("--interval", required=True, choices=[i.value for i in Interval])
    dl.add_argument("--since", type=int, default=None, help="Unix timestamp to start from")
    dl.add_argument("--max-bars", type=int, default=None, help="Max bars to fetch")

    # list
    sub.add_parser("list", help="List all datasets in the catalog")

    # combine
    comb = sub.add_parser("combine", help="Combine all sources for a symbol+interval")
    comb.add_argument("--symbol", required=True)
    comb.add_argument("--interval", required=True, choices=[i.value for i in Interval])

    # update
    sub.add_parser("update", help="Incrementally update all non-combined datasets")

    # validate
    val = sub.add_parser("validate", help="Validate a combined dataset")
    val.add_argument("--symbol", required=True)
    val.add_argument("--interval", required=True, choices=[i.value for i in Interval])

    # load-db
    ldb = sub.add_parser("load-db", help="Load CSV datasets into SQLite")
    ldb.add_argument(
        "--source", default=None,
        help="Only load entries with this source (e.g. 'combined')",
    )
    ldb.add_argument(
        "--db-url", default="sqlite+aiosqlite:///data/market_data.db",
        help="SQLite database URL",
    )

    return parser


async def cmd_download(args: argparse.Namespace) -> None:
    source = ProviderName(args.source)
    interval = Interval(args.interval)

    supported = PROVIDER_INTERVALS.get(source, set())
    if interval not in supported:
        print(f"Error: {source.value} does not support {interval.value}")
        labels = ", ".join(
            i.value for i in sorted(supported, key=lambda x: x.minutes)
        )
        print(f"Supported: {labels}")
        sys.exit(1)

    print(f"Downloading {args.symbol} {interval.value} from {source.value}...")
    bars = await download_from_provider(
        source, args.symbol, interval, args.since, args.max_bars,
    )

    if not bars:
        print("No data returned.")
        return

    file_path = save_bars(bars, args.symbol, source.value, interval.value)
    update_catalog_for_file(args.symbol, source.value, interval.value, file_path, bars)

    print(f"Downloaded {len(bars)} bars -> {file_path}")
    print(f"  Range: {bars[0].timestamp} - {bars[-1].timestamp}")


def cmd_list(_args: argparse.Namespace) -> None:
    catalog = load_catalog()
    if not catalog.entries:
        print("Catalog is empty.")
        return

    # Header
    fmt = "{:<10} {:<15} {:<8} {:>8} {:>14} {:>14} {}"
    print(fmt.format(
        "Symbol", "Source", "Interval", "Rows", "First TS", "Last TS", "Updated",
    ))
    print("-" * 90)
    for e in sorted(catalog.entries, key=lambda x: (x.symbol, x.source, x.interval)):
        print(fmt.format(
            e.symbol, e.source, e.interval, e.row_count,
            e.first_timestamp, e.last_timestamp, e.last_updated[:19],
        ))


def cmd_combine(args: argparse.Namespace) -> None:
    print(f"Combining {args.symbol} {args.interval}...")
    result = combine_datasets(args.symbol, args.interval)
    print(result.summary())


async def cmd_update(_args: argparse.Namespace) -> None:
    catalog = load_catalog()
    entries = [e for e in catalog.entries if e.source != "combined"]
    if not entries:
        print("No datasets to update.")
        return

    for entry in entries:
        source = ProviderName(entry.source)
        interval = Interval(entry.interval)
        print(f"Updating {entry.symbol} {entry.interval} from {entry.source}...")
        bars = await incremental_download(source, entry.symbol, interval)
        print(f"  -> {len(bars)} total bars")


def cmd_validate(args: argparse.Namespace) -> None:
    norm = normalize_symbol(args.symbol)
    catalog = load_catalog()
    entries = catalog.find(symbol=norm, source="combined", interval=args.interval)
    if not entries:
        print(f"No combined dataset found for {norm} {args.interval}")
        sys.exit(1)

    rows = load_csv(Path(entries[0].file_path))
    result = validate_dataset(rows)
    print(result.summary())


async def cmd_load_db(args: argparse.Namespace) -> None:
    print("Loading CSV datasets into SQLite...")
    db = Database(args.db_url)
    await db.initialize()
    try:
        results = await load_all_from_catalog(db, source_filter=args.source)
    finally:
        await db.close()

    total_files = len(results)
    total_rows = sum(results.values())
    print(f"\nLoaded {total_files} files, {total_rows:,} total rows into {args.db_url}")
    for path, count in results.items():
        print(f"  {path}: {count:,} rows")


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "download":
        await cmd_download(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "combine":
        cmd_combine(args)
    elif args.command == "update":
        await cmd_update(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "load-db":
        await cmd_load_db(args)


if __name__ == "__main__":
    asyncio.run(main())
