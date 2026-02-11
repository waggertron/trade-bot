"""Load CSV datasets into SQLite ohlc_bars table."""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.data.catalog import load_catalog
from src.db.database import Database
from src.db.models import OHLCRecord

logger = logging.getLogger(__name__)

DEFAULT_DB_URL = "sqlite+aiosqlite:///data/market_data.db"


async def load_csv_to_db(
    db: Database,
    file_path: Path,
    symbol: str,
    interval: str,
    source: str,
) -> int:
    """Read a CSV file and load its rows into the ohlc_bars table.

    Returns the number of rows loaded.
    """
    if not file_path.exists():
        logger.warning("File not found: %s", file_path)
        return 0

    records: list[OHLCRecord] = []
    with open(file_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(OHLCRecord(
                symbol=symbol,
                interval=interval,
                timestamp=int(row["timestamp"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
                source=source,
            ))

    if not records:
        return 0

    loaded = await db.load_ohlc_bars(records)
    logger.info("Loaded %d rows from %s", loaded, file_path)
    return loaded


async def load_all_from_catalog(
    db: Database,
    source_filter: str | None = None,
) -> dict[str, int]:
    """Load all catalog entries into the database.

    Args:
        db: Initialized Database instance.
        source_filter: If set, only load entries with this source (e.g. "combined").

    Returns:
        Dict mapping file_path -> row count loaded.
    """
    catalog = load_catalog()
    results: dict[str, int] = {}

    entries = catalog.entries
    if source_filter is not None:
        entries = [e for e in entries if e.source == source_filter]

    for entry in entries:
        count = await load_csv_to_db(
            db,
            Path(entry.file_path),
            entry.symbol,
            entry.interval,
            entry.source,
        )
        results[entry.file_path] = count

    return results


async def load_all(source_filter: str | None = None, db_url: str | None = None) -> dict[str, int]:
    """Convenience wrapper: create DB, load all catalog entries, close DB."""
    url = db_url or DEFAULT_DB_URL
    db = Database(url)
    await db.initialize()
    try:
        return await load_all_from_catalog(db, source_filter)
    finally:
        await db.close()
