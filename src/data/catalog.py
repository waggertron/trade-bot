from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

CATALOG_PATH = Path("data/catalog.json")


class DatasetEntry(BaseModel):
    symbol: str
    source: str
    interval: str
    file_path: str
    first_timestamp: int
    last_timestamp: int
    row_count: int
    last_updated: str  # ISO-8601


class Catalog:
    def __init__(self, entries: list[DatasetEntry] | None = None) -> None:
        self.entries: list[DatasetEntry] = entries or []

    def find(
        self,
        symbol: str | None = None,
        source: str | None = None,
        interval: str | None = None,
    ) -> list[DatasetEntry]:
        results = self.entries
        if symbol is not None:
            results = [e for e in results if e.symbol == symbol]
        if source is not None:
            results = [e for e in results if e.source == source]
        if interval is not None:
            results = [e for e in results if e.interval == interval]
        return results

    def upsert(self, entry: DatasetEntry) -> None:
        for i, existing in enumerate(self.entries):
            if (
                existing.symbol == entry.symbol
                and existing.source == entry.source
                and existing.interval == entry.interval
            ):
                self.entries[i] = entry
                return
        self.entries.append(entry)

    def remove(self, symbol: str, source: str, interval: str) -> bool:
        before = len(self.entries)
        self.entries = [
            e for e in self.entries
            if not (e.symbol == symbol and e.source == source and e.interval == interval)
        ]
        return len(self.entries) < before


def load_catalog(path: Path | None = None) -> Catalog:
    path = path or CATALOG_PATH
    if not path.exists():
        return Catalog()
    data = json.loads(path.read_text())
    entries = [DatasetEntry(**item) for item in data]
    return Catalog(entries)


def save_catalog(catalog: Catalog, path: Path | None = None) -> None:
    path = path or CATALOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [e.model_dump() for e in catalog.entries]
    path.write_text(json.dumps(data, indent=2) + "\n")
