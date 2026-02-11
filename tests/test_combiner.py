from __future__ import annotations

import csv
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from src.data.catalog import Catalog, DatasetEntry, save_catalog
from src.data.combiner import combine_datasets, validate_dataset
from src.data.providers.base import CSV_COLUMNS

if TYPE_CHECKING:
    from pathlib import Path


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _make_row(ts: int, close: str = "100.0", source: str = "kraken") -> dict:
    return {
        "timestamp": ts,
        "open": "99.0",
        "high": "101.0",
        "low": "98.0",
        "close": close,
        "volume": "50.0",
    }


class TestValidateDataset:
    def test_empty(self):
        result = validate_dataset([])
        assert result.is_valid is True
        assert result.row_count == 0

    def test_valid_data(self):
        rows = [_make_row(1000), _make_row(2000), _make_row(3000)]
        result = validate_dataset(rows)
        assert result.is_valid is True
        assert result.row_count == 3

    def test_duplicate_timestamps(self):
        rows = [_make_row(1000), _make_row(1000), _make_row(2000)]
        result = validate_dataset(rows)
        assert result.is_valid is False
        assert any("duplicate" in e for e in result.errors)

    def test_out_of_order(self):
        rows = [_make_row(2000), _make_row(1000), _make_row(3000)]
        result = validate_dataset(rows)
        assert result.is_valid is False
        assert any("out-of-order" in e for e in result.errors)

    def test_zero_prices(self):
        row = _make_row(1000, close="0")
        row["open"] = "0"
        row["high"] = "0"
        row["low"] = "0"
        rows = [row]
        result = validate_dataset(rows)
        assert result.is_valid is False
        assert any("invalid/zero prices" in e for e in result.errors)

    def test_gap_warning(self):
        # Normal interval ~1000s, then huge gap
        rows = [_make_row(1000), _make_row(2000), _make_row(3000), _make_row(100000)]
        result = validate_dataset(rows)
        assert result.is_valid is True
        assert any("gap" in w for w in result.warnings)

    def test_no_gap_warning_uniform(self):
        rows = [_make_row(i * 3600) for i in range(10)]
        result = validate_dataset(rows)
        assert result.warnings == []


class TestCombineDatasets:
    def test_merge_two_sources_priority(self, tmp_path: Path):
        """Higher-priority source wins on overlapping timestamps."""
        # Source A: cryptocompare (priority=4), timestamps 1,2,3,5,6
        src_a_path = tmp_path / "BTCUSD" / "cryptocompare_1d.csv"
        _write_csv(src_a_path, [
            _make_row(1, close="100.0"),
            _make_row(2, close="200.0"),
            _make_row(3, close="300.0"),
            _make_row(5, close="500.0"),
            _make_row(6, close="600.0"),
        ])

        # Source B: kraken (priority=2), timestamps 2,3,4,5
        src_b_path = tmp_path / "BTCUSD" / "kraken_1d.csv"
        _write_csv(src_b_path, [
            _make_row(2, close="201.0"),
            _make_row(3, close="301.0"),
            _make_row(4, close="400.0"),
            _make_row(5, close="501.0"),
        ])

        catalog = Catalog()
        catalog.upsert(DatasetEntry(
            symbol="BTCUSD", source="cryptocompare", interval="1d",
            file_path=str(src_a_path),
            first_timestamp=1, last_timestamp=6, row_count=5,
            last_updated="2024-01-01T00:00:00+00:00",
        ))
        catalog.upsert(DatasetEntry(
            symbol="BTCUSD", source="kraken", interval="1d",
            file_path=str(src_b_path),
            first_timestamp=2, last_timestamp=5, row_count=4,
            last_updated="2024-01-01T00:00:00+00:00",
        ))

        catalog_path = tmp_path / "catalog.json"
        save_catalog(catalog, catalog_path)

        with (
            patch("src.data.combiner.DATA_DIR", tmp_path),
            patch("src.data.catalog.CATALOG_PATH", catalog_path),
        ):
            result = combine_datasets("BTC/USD", "1d")

        assert result.is_valid is True
        assert result.row_count == 6

        # Read the combined file and verify priorities
        combined_path = tmp_path / "BTCUSD" / "combined_1d.csv"
        assert combined_path.exists()

        with open(combined_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 6
        # ts=1 from A only
        assert rows[0]["close"] == "100.0"
        # ts=2 from A (higher priority)
        assert rows[1]["close"] == "200.0"
        # ts=3 from A (higher priority)
        assert rows[2]["close"] == "300.0"
        # ts=4 from B (only source, fills gap)
        assert rows[3]["close"] == "400.0"
        # ts=5 from A (higher priority)
        assert rows[4]["close"] == "500.0"
        # ts=6 from A only
        assert rows[5]["close"] == "600.0"

    def test_no_datasets(self, tmp_path: Path):
        catalog_path = tmp_path / "catalog.json"
        save_catalog(Catalog(), catalog_path)

        with (
            patch("src.data.combiner.DATA_DIR", tmp_path),
            patch("src.data.catalog.CATALOG_PATH", catalog_path),
        ):
            result = combine_datasets("BTC/USD", "1d")

        assert result.is_valid is False
        assert any("No datasets" in e for e in result.errors)

    def test_excludes_combined_source(self, tmp_path: Path):
        """Existing combined entries should not feed into a new combine."""
        src_path = tmp_path / "BTCUSD" / "kraken_1d.csv"
        _write_csv(src_path, [_make_row(1000, close="100.0")])

        combined_path = tmp_path / "BTCUSD" / "combined_1d.csv"
        _write_csv(combined_path, [_make_row(1000, close="999.0")])

        catalog = Catalog()
        catalog.upsert(DatasetEntry(
            symbol="BTCUSD", source="kraken", interval="1d",
            file_path=str(src_path),
            first_timestamp=1000, last_timestamp=1000, row_count=1,
            last_updated="2024-01-01T00:00:00+00:00",
        ))
        catalog.upsert(DatasetEntry(
            symbol="BTCUSD", source="combined", interval="1d",
            file_path=str(combined_path),
            first_timestamp=1000, last_timestamp=1000, row_count=1,
            last_updated="2024-01-01T00:00:00+00:00",
        ))

        catalog_path = tmp_path / "catalog.json"
        save_catalog(catalog, catalog_path)

        with (
            patch("src.data.combiner.DATA_DIR", tmp_path),
            patch("src.data.catalog.CATALOG_PATH", catalog_path),
        ):
            result = combine_datasets("BTC/USD", "1d")

        assert result.row_count == 1

        # Read and verify it used kraken's value, not the old combined
        with open(tmp_path / "BTCUSD" / "combined_1d.csv") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["close"] == "100.0"

    def test_updates_catalog(self, tmp_path: Path):
        src_path = tmp_path / "BTCUSD" / "kraken_1d.csv"
        _write_csv(src_path, [_make_row(1000), _make_row(2000)])

        catalog = Catalog()
        catalog.upsert(DatasetEntry(
            symbol="BTCUSD", source="kraken", interval="1d",
            file_path=str(src_path),
            first_timestamp=1000, last_timestamp=2000, row_count=2,
            last_updated="2024-01-01T00:00:00+00:00",
        ))

        catalog_path = tmp_path / "catalog.json"
        save_catalog(catalog, catalog_path)

        with (
            patch("src.data.combiner.DATA_DIR", tmp_path),
            patch("src.data.catalog.CATALOG_PATH", catalog_path),
        ):
            combine_datasets("BTC/USD", "1d")

        # Reload catalog and check for combined entry
        from src.data.catalog import load_catalog as _load

        reloaded = _load(catalog_path)
        combined_entries = reloaded.find(source="combined")
        assert len(combined_entries) == 1
        assert combined_entries[0].row_count == 2
        assert combined_entries[0].first_timestamp == 1000
        assert combined_entries[0].last_timestamp == 2000
