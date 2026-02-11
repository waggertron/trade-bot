from __future__ import annotations

import asyncio
import csv
import logging
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from src.core.models import AssetType, MarketTick
from src.data.catalog import DatasetEntry, load_catalog, save_catalog
from src.data.providers import get_provider_download
from src.data.providers.base import (
    CSV_COLUMNS,
    Interval,
    OHLCBar,
    ProviderName,
    normalize_symbol,
)

logger = logging.getLogger(__name__)

# Kraken interval values (minutes)
VALID_INTERVALS = {1, 5, 15, 30, 60, 240, 1440}

DATA_DIR = Path("data")

_MINUTES_TO_INTERVAL: dict[int, Interval] = {
    1: Interval.M1,
    5: Interval.M5,
    15: Interval.M15,
    30: Interval.M30,
    60: Interval.H1,
    240: Interval.H4,
    1440: Interval.D1,
    10080: Interval.W1,
}


async def download_ohlc(
    symbol: str,
    interval: int = 60,
    since: int | None = None,
    max_bars: int | None = None,
) -> list[dict[str, Any]]:
    """Download OHLC data from Kraken's public API with pagination.

    Args:
        symbol: Trading pair like "BTC/USD"
        interval: Candle interval in minutes (1, 5, 15, 30, 60, 240, 1440)
        since: Unix timestamp to start from (optional)
        max_bars: Maximum number of bars to fetch (optional, fetches all available if None)

    Returns:
        List of OHLC dicts with keys: timestamp, open, high, low, close, volume
    """
    if interval not in VALID_INTERVALS:
        raise ValueError(
            f"Invalid interval {interval}. Must be one of {sorted(VALID_INTERVALS)}"
        )

    pair = symbol.replace("/", "")
    all_bars: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            params: dict[str, str | int] = {"pair": pair, "interval": interval}
            if since is not None:
                params["since"] = since

            resp = await client.get(
                "https://api.kraken.com/0/public/OHLC",
                params=params,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()

            if data.get("error"):
                raise RuntimeError(f"Kraken API error: {data['error']}")

            result: dict[str, Any] = data["result"]
            # The result contains the pair data and a "last" timestamp
            last = result.pop("last", None)
            pair_data: list[Any] = next(iter(result.values()), [])

            if not pair_data:
                break

            for row in pair_data:
                # Kraken OHLC format: [time, open, high, low, close, vwap, volume, count]
                all_bars.append({
                    "timestamp": int(row[0]),
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[6],
                })

            logger.info("Fetched %d bars (total: %d)", len(pair_data), len(all_bars))

            if max_bars and len(all_bars) >= max_bars:
                all_bars = all_bars[:max_bars]
                break

            # If we got fewer than 720 bars, we've reached the end
            if len(pair_data) < 720:
                break

            # Use "last" for pagination
            if last is not None:
                since = int(last)
            else:
                break

            # Rate limit: Kraken allows ~1 req/sec for public endpoints
            await asyncio.sleep(1.0)

    return all_bars


def save_to_csv(bars: list[dict[str, Any]], symbol: str, interval: int) -> Path:
    """Save OHLC bars to CSV file in the data/ directory."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pair = symbol.replace("/", "")
    filename = DATA_DIR / f"{pair}_{interval}m.csv"

    fieldnames = ["timestamp", "open", "high", "low", "close", "volume"]
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(bars)

    logger.info("Saved %d bars to %s", len(bars), filename)
    return filename


def load_csv(filepath: Path) -> list[dict[str, Any]]:
    """Load OHLC bars from a CSV file."""
    with open(filepath) as f:
        reader = csv.DictReader(f)
        return list(reader)


def bars_to_ticks(bars: list[dict[str, Any]], symbol: str) -> list[MarketTick]:
    """Convert OHLC bars to MarketTick objects using close price."""
    ticks: list[MarketTick] = []
    for bar in bars:
        ticks.append(MarketTick(
            symbol=symbol,
            price=Decimal(str(bar["close"])),
            volume=int(float(bar["volume"])),
            timestamp=datetime.fromtimestamp(int(bar["timestamp"]), tz=UTC),
            asset_type=AssetType.CRYPTO,
        ))
    return ticks


# ---------------------------------------------------------------------------
# Provider-aware functions
# ---------------------------------------------------------------------------


def _interval_from_minutes(minutes: int) -> Interval:
    """Map legacy integer interval (in minutes) to Interval enum."""
    iv = _MINUTES_TO_INTERVAL.get(minutes)
    if iv is None:
        raise ValueError(f"No Interval mapping for {minutes} minutes")
    return iv


async def download_from_provider(
    source: str | ProviderName,
    symbol: str,
    interval: str | Interval,
    since: int | None = None,
    max_bars: int | None = None,
) -> list[OHLCBar]:
    """Download OHLC data from a named provider."""
    if isinstance(source, str):
        source = ProviderName(source)
    if isinstance(interval, str):
        interval = Interval(interval)
    fn = get_provider_download(source)
    return await fn(symbol=symbol, interval=interval, since=since, max_bars=max_bars)


def save_bars(
    bars: list[OHLCBar],
    symbol: str,
    source: str,
    interval: str,
) -> Path:
    """Save OHLCBar list to data/{SYMBOL}/{source}_{interval}.csv."""
    norm = normalize_symbol(symbol)
    symbol_dir = DATA_DIR / norm
    symbol_dir.mkdir(parents=True, exist_ok=True)
    out_path = symbol_dir / f"{source}_{interval}.csv"

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for bar in bars:
            writer.writerow(bar.to_dict())

    logger.info("Saved %d bars to %s", len(bars), out_path)
    return out_path


def update_catalog_for_file(
    symbol: str,
    source: str,
    interval: str,
    file_path: Path,
    bars: list[OHLCBar],
) -> None:
    """Update the catalog after saving a dataset."""
    if not bars:
        return
    catalog = load_catalog()
    now = datetime.now(UTC).isoformat()
    catalog.upsert(DatasetEntry(
        symbol=normalize_symbol(symbol),
        source=source,
        interval=interval,
        file_path=str(file_path),
        first_timestamp=bars[0].timestamp,
        last_timestamp=bars[-1].timestamp,
        row_count=len(bars),
        last_updated=now,
    ))
    save_catalog(catalog)


async def incremental_download(
    source: str | ProviderName,
    symbol: str,
    interval: str | Interval,
) -> list[OHLCBar]:
    """Check catalog for last timestamp, fetch new data, merge, deduplicate, and save."""
    if isinstance(source, str):
        source = ProviderName(source)
    if isinstance(interval, str):
        interval = Interval(interval)

    norm = normalize_symbol(symbol)
    catalog = load_catalog()
    entries = catalog.find(symbol=norm, source=source.value, interval=interval.value)

    since: int | None = None
    existing_bars: list[OHLCBar] = []

    if entries:
        entry = entries[0]
        since = entry.last_timestamp
        # Load existing data
        filepath = Path(entry.file_path)
        if filepath.exists():
            with open(filepath) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_bars.append(OHLCBar(
                        timestamp=int(row["timestamp"]),
                        open=row["open"],
                        high=row["high"],
                        low=row["low"],
                        close=row["close"],
                        volume=row["volume"],
                        source=source.value,
                    ))

    new_bars = await download_from_provider(source, symbol, interval, since=since)

    # Merge and deduplicate by timestamp
    by_ts: dict[int, OHLCBar] = {}
    for bar in existing_bars:
        by_ts[bar.timestamp] = bar
    for bar in new_bars:
        by_ts[bar.timestamp] = bar  # new data overwrites old

    all_bars = sorted(by_ts.values(), key=lambda b: b.timestamp)

    file_path = save_bars(all_bars, symbol, source.value, interval.value)
    update_catalog_for_file(
        symbol, source.value, interval.value, file_path, all_bars,
    )

    logger.info(
        "Incremental update: %d existing + %d new -> %d total bars",
        len(existing_bars), len(new_bars), len(all_bars),
    )
    return all_bars
