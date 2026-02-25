"""Tests for the simulation disk cache."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from src.data.providers.base import OHLCBar
from src.simulation.cache import BarCache, ReportCache
from src.simulation.models import SimulationConfig

if TYPE_CHECKING:
    from pathlib import Path


def _make_bars(n: int = 3, start_price: float = 100.0) -> list[OHLCBar]:
    """Create n daily bars."""
    bars = []
    base_ts = 1700000000
    for i in range(n):
        price = start_price + i * 0.5
        bars.append(
            OHLCBar(
                timestamp=base_ts + i * 86400,
                open=str(price - 0.2),
                high=str(price + 1.0),
                low=str(price - 1.0),
                close=str(price),
                volume=str(1000000),
                source="yfinance",
            )
        )
    return bars


# ---------------------------------------------------------------------------
# BarCache tests
# ---------------------------------------------------------------------------


class TestBarCache:
    def test_get_returns_none_on_miss(self, tmp_path: Path) -> None:
        cache = BarCache(cache_dir=tmp_path)
        assert cache.get("AAPL") is None

    def test_put_then_get_returns_bars(self, tmp_path: Path) -> None:
        cache = BarCache(cache_dir=tmp_path)
        bars = _make_bars(3)
        cache.put("AAPL", bars)
        result = cache.get("AAPL")
        assert result is not None
        assert len(result) == 3
        assert result[0].close == bars[0].close
        assert result[2].timestamp == bars[2].timestamp

    def test_different_symbols_are_separate(self, tmp_path: Path) -> None:
        cache = BarCache(cache_dir=tmp_path)
        aapl_bars = _make_bars(2, start_price=150.0)
        msft_bars = _make_bars(4, start_price=300.0)
        cache.put("AAPL", aapl_bars)
        cache.put("MSFT", msft_bars)
        assert len(cache.get("AAPL")) == 2
        assert len(cache.get("MSFT")) == 4
        assert cache.get("AAPL")[0].close != cache.get("MSFT")[0].close

    def test_stale_cache_misses_on_new_day(self, tmp_path: Path) -> None:
        cache = BarCache(cache_dir=tmp_path)
        bars = _make_bars(3)

        with patch.object(cache, "_today_str", return_value="2026-02-19"):
            cache.put("AAPL", bars)

        with patch.object(cache, "_today_str", return_value="2026-02-20"):
            assert cache.get("AAPL") is None

    def test_corrupt_cache_returns_none(self, tmp_path: Path) -> None:
        cache = BarCache(cache_dir=tmp_path)
        bars = _make_bars(2)
        cache.put("AAPL", bars)

        # Corrupt the file
        cache_files = list(tmp_path.glob("*.json"))
        assert len(cache_files) == 1
        cache_files[0].write_text("NOT VALID JSON {{{")

        assert cache.get("AAPL") is None

    def test_clear_removes_files(self, tmp_path: Path) -> None:
        cache = BarCache(cache_dir=tmp_path)
        cache.put("AAPL", _make_bars(2))
        cache.put("MSFT", _make_bars(3))
        assert len(list(tmp_path.glob("*.json"))) == 2
        cache.clear()
        assert len(list(tmp_path.glob("*.json"))) == 0


# ---------------------------------------------------------------------------
# ReportCache tests
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> SimulationConfig:
    defaults = dict(
        stocks=["AAPL"],
        initial_balance=10000.0,
        train_days=60,
        test_days=30,
        mc_simulations=100,
        mc_seed=42,
    )
    defaults.update(overrides)
    return SimulationConfig(**defaults)


def _make_report_dict(config: SimulationConfig) -> dict:
    """Minimal report dict for caching."""
    return {
        "id": "test123",
        "status": "completed",
        "config": config.model_dump(),
        "risk_level_results": {},
        "recommendation": None,
        "started_at": "2026-01-01T00:00:00",
        "completed_at": "2026-01-01T00:01:00",
        "error": None,
    }


class TestReportCache:
    def test_get_returns_none_on_miss(self, tmp_path: Path) -> None:
        cache = ReportCache(cache_dir=tmp_path)
        config = _make_config()
        assert cache.get(config) is None

    def test_put_then_get_returns_report(self, tmp_path: Path) -> None:
        cache = ReportCache(cache_dir=tmp_path)
        config = _make_config()
        report = _make_report_dict(config)
        cache.put(config, report)
        result = cache.get(config)
        assert result is not None
        assert result["id"] == "test123"
        assert result["status"] == "completed"

    def test_different_configs_are_separate(self, tmp_path: Path) -> None:
        cache = ReportCache(cache_dir=tmp_path)
        config_a = _make_config(stocks=["AAPL"])
        config_b = _make_config(stocks=["MSFT"])
        report_a = _make_report_dict(config_a)
        report_b = _make_report_dict(config_b)
        report_b["id"] = "other456"

        cache.put(config_a, report_a)
        cache.put(config_b, report_b)
        assert cache.get(config_a)["id"] == "test123"
        assert cache.get(config_b)["id"] == "other456"

    def test_config_hash_is_deterministic(self, tmp_path: Path) -> None:
        cache = ReportCache(cache_dir=tmp_path)
        config1 = _make_config()
        config2 = _make_config()
        assert cache._config_hash(config1) == cache._config_hash(config2)

    def test_stale_cache_misses_on_new_day(self, tmp_path: Path) -> None:
        cache = ReportCache(cache_dir=tmp_path)
        config = _make_config()
        report = _make_report_dict(config)

        with patch.object(cache, "_today_str", return_value="2026-02-19"):
            cache.put(config, report)

        with patch.object(cache, "_today_str", return_value="2026-02-20"):
            assert cache.get(config) is None

    def test_clear_removes_files(self, tmp_path: Path) -> None:
        cache = ReportCache(cache_dir=tmp_path)
        config_a = _make_config(stocks=["AAPL"])
        config_b = _make_config(stocks=["MSFT"])
        cache.put(config_a, _make_report_dict(config_a))
        cache.put(config_b, _make_report_dict(config_b))
        assert len(list(tmp_path.glob("*.json"))) == 2
        cache.clear()
        assert len(list(tmp_path.glob("*.json"))) == 0
