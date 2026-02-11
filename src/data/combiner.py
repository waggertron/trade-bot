from __future__ import annotations

import csv
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.data.catalog import DatasetEntry, load_catalog, save_catalog
from src.data.providers import SOURCE_PRIORITY
from src.data.providers.base import CSV_COLUMNS, normalize_symbol

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


class ValidationResult(BaseModel):
    is_valid: bool
    row_count: int
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def summary(self) -> str:
        lines = [f"Rows: {self.row_count}, Valid: {self.is_valid}"]
        for e in self.errors:
            lines.append(f"  ERROR: {e}")
        for w in self.warnings:
            lines.append(f"  WARNING: {w}")
        return "\n".join(lines)


def validate_dataset(rows: list[dict[str, Any]]) -> ValidationResult:
    """Validate a list of OHLC rows for common data quality issues."""
    errors: list[str] = []
    warnings: list[str] = []

    if not rows:
        return ValidationResult(is_valid=True, row_count=0)

    # Check for duplicate timestamps
    timestamps = [int(r["timestamp"]) for r in rows]
    seen: set[int] = set()
    dupes = 0
    for ts in timestamps:
        if ts in seen:
            dupes += 1
        seen.add(ts)
    if dupes:
        errors.append(f"{dupes} duplicate timestamp(s)")

    # Check chronological order
    out_of_order = 0
    for i in range(1, len(timestamps)):
        if timestamps[i] <= timestamps[i - 1]:
            out_of_order += 1
    if out_of_order:
        errors.append(f"{out_of_order} out-of-order timestamp(s)")

    # Check for bad prices
    bad_prices = 0
    for r in rows:
        for col in ("open", "high", "low", "close"):
            try:
                val = float(r[col])
                if val <= 0:
                    bad_prices += 1
                    break
            except (ValueError, TypeError):
                bad_prices += 1
                break
    if bad_prices:
        errors.append(f"{bad_prices} row(s) with invalid/zero prices")

    # Check for gaps (> 5x median interval)
    if len(timestamps) > 2:
        intervals = [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
        intervals_sorted = sorted(intervals)
        median_interval = intervals_sorted[len(intervals_sorted) // 2]
        if median_interval > 0:
            gap_count = sum(1 for iv in intervals if iv > median_interval * 5)
            if gap_count:
                warnings.append(f"{gap_count} gap(s) exceeding 5x median interval")

    is_valid = len(errors) == 0
    return ValidationResult(
        is_valid=is_valid,
        row_count=len(rows),
        errors=errors,
        warnings=warnings,
    )


def combine_datasets(symbol: str, interval: str) -> ValidationResult:
    """Merge all datasets for a symbol+interval, preferring higher-priority sources.

    Returns a ValidationResult for the combined dataset.
    """
    catalog = load_catalog()
    norm = normalize_symbol(symbol)

    # Find all entries matching symbol+interval, excluding "combined" source
    entries = [
        e for e in catalog.find(symbol=norm, interval=interval)
        if e.source != "combined"
    ]

    if not entries:
        return ValidationResult(is_valid=False, row_count=0, errors=["No datasets found"])

    # Build priority lookup
    provider_priority: dict[str, int] = {
        p.value: pri for p, pri in SOURCE_PRIORITY.items()
    }

    # Read all rows from each source with their priorities
    merged: dict[int, tuple[int, dict[str, Any]]] = {}

    for entry in entries:
        filepath = Path(entry.file_path)
        if not filepath.exists():
            logger.warning("File not found: %s", filepath)
            continue

        priority = provider_priority.get(entry.source, 0)

        with open(filepath) as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = int(row["timestamp"])
                existing = merged.get(ts)
                if existing is None or priority > existing[0]:
                    merged[ts] = (priority, dict(row))

    if not merged:
        return ValidationResult(is_valid=False, row_count=0, errors=["No data after merge"])

    # Sort by timestamp
    sorted_rows = [row for _, (_, row) in sorted(merged.items())]

    # Validate
    result = validate_dataset(sorted_rows)

    # Write combined CSV
    symbol_dir = DATA_DIR / norm
    symbol_dir.mkdir(parents=True, exist_ok=True)
    out_path = symbol_dir / f"combined_{interval}.csv"

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow({col: row[col] for col in CSV_COLUMNS})

    logger.info("Combined %d rows -> %s", len(sorted_rows), out_path)

    # Update catalog
    now = datetime.now(UTC).isoformat()
    catalog.upsert(DatasetEntry(
        symbol=norm,
        source="combined",
        interval=interval,
        file_path=str(out_path),
        first_timestamp=int(sorted_rows[0]["timestamp"]),
        last_timestamp=int(sorted_rows[-1]["timestamp"]),
        row_count=len(sorted_rows),
        last_updated=now,
    ))
    save_catalog(catalog)

    return result
