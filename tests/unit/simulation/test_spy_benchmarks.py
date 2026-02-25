"""Tests for _run_spy_benchmarks helper — returns both B&H and DCA results."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the scripts directory importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from src.data.providers.base import OHLCBar, ProviderName


def _make_bars(n: int = 30, start_price: float = 100.0) -> list[OHLCBar]:
    bars = []
    for i in range(n):
        price = str(start_price + i * 0.5)
        bars.append(OHLCBar(
            timestamp=1700000000 + i * 86400,
            open=price, high=price, low=price, close=price,
            volume="1000000",
            source=ProviderName.YFINANCE.value,
        ))
    return bars


class TestRunSpyBenchmarks:
    def test_returns_both_buy_and_hold_and_dca(self):
        from compare_sentiment_backtest import _run_spy_benchmarks
        bars = _make_bars(30)
        bh, dca = _run_spy_benchmarks(bars, cash=10000.0)
        assert bh is not None
        assert dca is not None

    def test_buy_and_hold_result_has_name(self):
        from compare_sentiment_backtest import _run_spy_benchmarks
        bars = _make_bars(30)
        bh, _dca = _run_spy_benchmarks(bars, cash=10000.0)
        assert "Hold" in bh.name or "hold" in bh.name.lower()

    def test_dca_result_has_name(self):
        from compare_sentiment_backtest import _run_spy_benchmarks
        bars = _make_bars(30)
        _bh, dca = _run_spy_benchmarks(bars, cash=10000.0)
        assert "DCA" in dca.name or "dca" in dca.name.lower()

    def test_both_results_track_same_initial_cash(self):
        from compare_sentiment_backtest import _run_spy_benchmarks
        bars = _make_bars(30)
        bh, dca = _run_spy_benchmarks(bars, cash=10000.0)
        assert bh.initial_balance == pytest.approx(10000.0)
        assert dca.initial_balance == pytest.approx(10000.0)
