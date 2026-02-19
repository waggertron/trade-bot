"""Disk cache for simulation bar data and full reports."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from src.data.providers.base import OHLCBar
from src.simulation.models import SimulationConfig

logger = logging.getLogger(__name__)

_DEFAULT_BAR_DIR = Path("data/cache/bars")
_DEFAULT_REPORT_DIR = Path("data/cache/reports")


class BarCache:
    """Cache yfinance OHLC bars per symbol, keyed by (symbol, today_date).

    Layout: ``{cache_dir}/{SYMBOL}_{YYYY-MM-DD}.json``
    TTL is 24 h — the date in the filename acts as automatic expiry.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._dir = cache_dir or _DEFAULT_BAR_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _today_str(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _path(self, symbol: str) -> Path:
        return self._dir / f"{symbol}_{self._today_str()}.json"

    def get(self, symbol: str) -> list[OHLCBar] | None:
        path = self._path(symbol)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return [OHLCBar(**bar) for bar in data]
        except Exception:
            logger.debug("Corrupt bar cache for %s, ignoring", symbol)
            return None

    def put(self, symbol: str, bars: list[OHLCBar]) -> None:
        path = self._path(symbol)
        path.write_text(json.dumps([bar.model_dump() for bar in bars]))

    def clear(self) -> None:
        for f in self._dir.glob("*.json"):
            f.unlink()


class ReportCache:
    """Cache full simulation report dicts, keyed by config hash + today's date.

    Layout: ``{cache_dir}/{hash}_{YYYY-MM-DD}.json``
    Only caches when ``mc_seed is not None`` (deterministic results).
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._dir = cache_dir or _DEFAULT_REPORT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _today_str(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _config_hash(self, config: SimulationConfig) -> str:
        payload = json.dumps(config.model_dump(), sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def _path(self, config: SimulationConfig) -> Path:
        h = self._config_hash(config)
        return self._dir / f"{h}_{self._today_str()}.json"

    def get(self, config: SimulationConfig) -> dict | None:
        path = self._path(config)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except Exception:
            logger.debug("Corrupt report cache, ignoring")
            return None

    def put(self, config: SimulationConfig, report: dict) -> None:
        path = self._path(config)
        path.write_text(json.dumps(report, default=str))

    def clear(self) -> None:
        for f in self._dir.glob("*.json"):
            f.unlink()
