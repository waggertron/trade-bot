"""Tests for OHLC database loading and querying."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.data.db_loader import load_csv_to_db
from src.db.database import Database
from src.db.models import OHLCRecord


@pytest.fixture
async def db() -> Database:
    """Create an in-memory SQLite database for testing."""
    database = Database("sqlite+aiosqlite:///:memory:")
    await database.initialize()
    yield database  # type: ignore[misc]
    await database.close()


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create a sample CSV file for testing."""
    filepath = tmp_path / "test.csv"
    rows = [
        {
            "timestamp": "1000",
            "open": "100",
            "high": "110",
            "low": "90",
            "close": "105",
            "volume": "1000",
        },
        {
            "timestamp": "2000",
            "open": "105",
            "high": "115",
            "low": "95",
            "close": "110",
            "volume": "1100",
        },
        {
            "timestamp": "3000",
            "open": "110",
            "high": "120",
            "low": "100",
            "close": "115",
            "volume": "1200",
        },
    ]
    cols = ["timestamp", "open", "high", "low", "close", "volume"]
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)
    return filepath


async def test_load_and_query_roundtrip(db: Database, sample_csv: Path) -> None:
    """Load CSV, then query back and verify data matches."""
    count = await load_csv_to_db(db, sample_csv, "AAPL", "1d", "yfinance")
    assert count == 3

    rows = await db.query_ohlc_bars(symbol="AAPL", interval="1d")
    assert len(rows) == 3
    assert rows[0].timestamp == 1000
    assert rows[0].open == "100"
    assert rows[0].close == "105"
    assert rows[2].timestamp == 3000


async def test_upsert_idempotency(db: Database, sample_csv: Path) -> None:
    """Loading the same data twice should not create duplicates."""
    await load_csv_to_db(db, sample_csv, "AAPL", "1d", "yfinance")
    await load_csv_to_db(db, sample_csv, "AAPL", "1d", "yfinance")

    total = await db.count_ohlc_bars(symbol="AAPL", interval="1d")
    assert total == 3  # no duplicates


async def test_time_range_query(db: Database, sample_csv: Path) -> None:
    """Query with start_ts/end_ts filters."""
    await load_csv_to_db(db, sample_csv, "AAPL", "1d", "yfinance")

    rows = await db.query_ohlc_bars(symbol="AAPL", interval="1d", start_ts=1500, end_ts=2500)
    assert len(rows) == 1
    assert rows[0].timestamp == 2000


async def test_count_ohlc_bars(db: Database, sample_csv: Path) -> None:
    """Count rows with filters."""
    await load_csv_to_db(db, sample_csv, "AAPL", "1d", "yfinance")
    await load_csv_to_db(db, sample_csv, "MSFT", "1d", "yfinance")

    assert await db.count_ohlc_bars() == 6
    assert await db.count_ohlc_bars(symbol="AAPL") == 3
    assert await db.count_ohlc_bars(symbol="MSFT") == 3
    assert await db.count_ohlc_bars(symbol="GOOG") == 0


async def test_load_ohlc_bars_directly(db: Database) -> None:
    """Test the load_ohlc_bars method directly."""
    records = [
        OHLCRecord(
            symbol="SPY",
            interval="1d",
            timestamp=i * 1000,
            open="100",
            high="110",
            low="90",
            close="105",
            volume="500",
            source="yfinance",
        )
        for i in range(1, 4)
    ]
    loaded = await db.load_ohlc_bars(records)
    assert loaded == 3

    rows = await db.query_ohlc_bars(symbol="SPY")
    assert len(rows) == 3


async def test_query_with_source_filter(db: Database) -> None:
    """Query bars filtered by source."""
    records_a = [
        OHLCRecord(
            symbol="BTCUSD",
            interval="1d",
            timestamp=1000,
            open="50000",
            high="51000",
            low="49000",
            close="50500",
            volume="100",
            source="cryptocompare",
        ),
    ]
    records_b = [
        OHLCRecord(
            symbol="BTCUSD",
            interval="1d",
            timestamp=2000,
            open="50500",
            high="52000",
            low="50000",
            close="51500",
            volume="200",
            source="binance",
        ),
    ]
    await db.load_ohlc_bars(records_a)
    await db.load_ohlc_bars(records_b)

    cc_rows = await db.query_ohlc_bars(symbol="BTCUSD", source="cryptocompare")
    assert len(cc_rows) == 1
    assert cc_rows[0].source == "cryptocompare"

    bn_rows = await db.query_ohlc_bars(symbol="BTCUSD", source="binance")
    assert len(bn_rows) == 1
    assert bn_rows[0].source == "binance"


async def test_load_missing_file(db: Database) -> None:
    """Loading a nonexistent file should return 0."""
    count = await load_csv_to_db(db, Path("/nonexistent/file.csv"), "X", "1d", "test")
    assert count == 0
