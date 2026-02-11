from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.data.catalog import Catalog, DatasetEntry, load_catalog, save_catalog

if TYPE_CHECKING:
    from pathlib import Path


def _entry(
    symbol: str = "BTCUSD",
    source: str = "kraken",
    interval: str = "1h",
    **kwargs,
) -> DatasetEntry:
    defaults = {
        "file_path": f"data/{symbol}/{source}_{interval}.csv",
        "first_timestamp": 1000000,
        "last_timestamp": 2000000,
        "row_count": 100,
        "last_updated": "2024-01-01T00:00:00+00:00",
    }
    defaults.update(kwargs)
    return DatasetEntry(symbol=symbol, source=source, interval=interval, **defaults)


class TestCatalog:
    def test_empty_catalog(self):
        c = Catalog()
        assert c.entries == []
        assert c.find() == []

    def test_upsert_adds_new(self):
        c = Catalog()
        e = _entry()
        c.upsert(e)
        assert len(c.entries) == 1
        assert c.entries[0] is e

    def test_upsert_replaces_existing(self):
        c = Catalog()
        e1 = _entry(row_count=100)
        e2 = _entry(row_count=200)
        c.upsert(e1)
        c.upsert(e2)
        assert len(c.entries) == 1
        assert c.entries[0].row_count == 200

    def test_upsert_different_source(self):
        c = Catalog()
        c.upsert(_entry(source="kraken"))
        c.upsert(_entry(source="binance"))
        assert len(c.entries) == 2

    def test_find_by_symbol(self):
        c = Catalog()
        c.upsert(_entry(symbol="BTCUSD"))
        c.upsert(_entry(symbol="ETHUSD"))
        results = c.find(symbol="BTCUSD")
        assert len(results) == 1
        assert results[0].symbol == "BTCUSD"

    def test_find_by_source(self):
        c = Catalog()
        c.upsert(_entry(source="kraken"))
        c.upsert(_entry(source="binance"))
        results = c.find(source="kraken")
        assert len(results) == 1

    def test_find_by_interval(self):
        c = Catalog()
        c.upsert(_entry(interval="1h"))
        c.upsert(_entry(interval="1d"))
        results = c.find(interval="1d")
        assert len(results) == 1

    def test_find_multiple_filters(self):
        c = Catalog()
        c.upsert(_entry(symbol="BTCUSD", source="kraken", interval="1h"))
        c.upsert(_entry(symbol="BTCUSD", source="binance", interval="1h"))
        c.upsert(_entry(symbol="ETHUSD", source="kraken", interval="1h"))
        results = c.find(symbol="BTCUSD", source="kraken")
        assert len(results) == 1

    def test_remove(self):
        c = Catalog()
        c.upsert(_entry(symbol="BTCUSD", source="kraken", interval="1h"))
        c.upsert(_entry(symbol="ETHUSD", source="kraken", interval="1h"))
        removed = c.remove("BTCUSD", "kraken", "1h")
        assert removed is True
        assert len(c.entries) == 1
        assert c.entries[0].symbol == "ETHUSD"

    def test_remove_nonexistent(self):
        c = Catalog()
        c.upsert(_entry())
        removed = c.remove("ETHUSD", "kraken", "1h")
        assert removed is False
        assert len(c.entries) == 1


class TestCatalogPersistence:
    def test_save_and_load_roundtrip(self, tmp_path: Path):
        path = tmp_path / "catalog.json"
        c = Catalog()
        c.upsert(_entry(symbol="BTCUSD", source="kraken", interval="1h"))
        c.upsert(_entry(symbol="ETHUSD", source="binance", interval="1d"))

        save_catalog(c, path)
        loaded = load_catalog(path)

        assert len(loaded.entries) == 2
        assert loaded.entries[0].symbol == "BTCUSD"
        assert loaded.entries[1].source == "binance"

    def test_load_missing_file(self, tmp_path: Path):
        path = tmp_path / "missing.json"
        c = load_catalog(path)
        assert c.entries == []

    def test_save_creates_parent_dirs(self, tmp_path: Path):
        path = tmp_path / "sub" / "dir" / "catalog.json"
        c = Catalog()
        c.upsert(_entry())
        save_catalog(c, path)
        assert path.exists()

    def test_saved_json_format(self, tmp_path: Path):
        path = tmp_path / "catalog.json"
        c = Catalog()
        c.upsert(_entry(symbol="BTCUSD"))
        save_catalog(c, path)

        data = json.loads(path.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["symbol"] == "BTCUSD"
        assert "file_path" in data[0]
