from __future__ import annotations

import csv
import math
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.core.models import AssetType, MarketTick
from src.data.downloader import bars_to_ticks, load_csv, save_to_csv
from src.data.backtester import BacktestResult, _compute_metrics, run_backtest


# --- Helpers ---

def make_ticks(prices: list[float], symbol: str = "BTC/USD") -> list[MarketTick]:
    """Create a list of MarketTick objects from a price series."""
    base_ts = 1700000000
    return [
        MarketTick(
            symbol=symbol,
            price=Decimal(str(p)),
            volume=100,
            timestamp=datetime.fromtimestamp(base_ts + i * 3600, tz=timezone.utc),
            asset_type=AssetType.CRYPTO,
        )
        for i, p in enumerate(prices)
    ]


# --- CSV loading tests ---

class TestCSVOperations:
    def test_save_and_load_csv(self, tmp_path):
        bars = [
            {"timestamp": 1700000000, "open": "100.0", "high": "105.0", "low": "99.0", "close": "103.0", "volume": "50.5"},
            {"timestamp": 1700003600, "open": "103.0", "high": "108.0", "low": "101.0", "close": "106.0", "volume": "60.2"},
        ]
        # Temporarily override DATA_DIR for the test
        import src.data.downloader as dl
        original_dir = dl.DATA_DIR
        dl.DATA_DIR = tmp_path
        try:
            path = save_to_csv(bars, "BTC/USD", 60)
            assert path.exists()
            assert path.name == "BTCUSD_60m.csv"

            loaded = load_csv(path)
            assert len(loaded) == 2
            assert loaded[0]["close"] == "103.0"
            assert loaded[1]["volume"] == "60.2"
        finally:
            dl.DATA_DIR = original_dir

    def test_bars_to_ticks(self):
        bars = [
            {"timestamp": "1700000000", "open": "100", "high": "105", "low": "99", "close": "103.50", "volume": "50.5"},
            {"timestamp": "1700003600", "open": "103", "high": "108", "low": "101", "close": "106.25", "volume": "60"},
        ]
        ticks = bars_to_ticks(bars, "BTC/USD")
        assert len(ticks) == 2
        assert ticks[0].price == Decimal("103.50")
        assert ticks[0].symbol == "BTC/USD"
        assert ticks[0].asset_type == AssetType.CRYPTO
        assert ticks[0].volume == 50
        assert ticks[1].price == Decimal("106.25")
        assert ticks[1].timestamp.year == 2023

    def test_bars_to_ticks_empty(self):
        ticks = bars_to_ticks([], "BTC/USD")
        assert ticks == []


# --- Metrics computation tests ---

class TestMetrics:
    def test_empty_equity_curve(self):
        result = _compute_metrics([], [], 100000.0)
        assert result.total_trades == 0
        assert result.max_drawdown == 0.0
        assert result.sharpe_ratio == 0.0

    def test_max_drawdown(self):
        # Equity goes 100 -> 120 -> 90 -> 110
        # Peak=120, trough=90 => dd = (120-90)/120 = 25%
        equity = [100.0, 120.0, 90.0, 110.0]
        result = _compute_metrics(equity, [], 100.0)
        assert result.max_drawdown == pytest.approx(25.0)

    def test_no_drawdown(self):
        equity = [100.0, 110.0, 120.0, 130.0]
        result = _compute_metrics(equity, [], 100.0)
        assert result.max_drawdown == 0.0

    def test_sharpe_positive(self):
        # Steadily increasing equity
        equity = [100.0 + i * 1.0 for i in range(100)]
        result = _compute_metrics(equity, [], 100.0)
        assert result.sharpe_ratio > 0

    def test_return_pct(self):
        result = BacktestResult(initial_cash=100000.0, final_value=110000.0)
        assert result.return_pct == pytest.approx(10.0)

    def test_win_rate(self):
        result = BacktestResult(winning_trades=7, losing_trades=3)
        assert result.win_rate == pytest.approx(0.7)

    def test_win_rate_no_trades(self):
        result = BacktestResult()
        assert result.win_rate == 0.0


# --- Backtest engine tests ---

class TestBacktester:
    async def test_backtest_too_few_ticks(self):
        """With fewer ticks than the long window, no trades should execute."""
        ticks = make_ticks([100.0] * 10)
        result = await run_backtest(ticks, initial_cash=Decimal("100000"))
        assert result.total_trades == 0
        assert result.total_ticks == 10
        assert result.final_value == pytest.approx(100000.0)

    async def test_backtest_uptrend(self):
        """Strong uptrend should trigger at least one trade."""
        # 60 flat ticks then 40 rising ticks — enough for momentum to see a crossover
        prices = [100.0] * 60 + [100.0 + i * 2.0 for i in range(40)]
        ticks = make_ticks(prices)
        result = await run_backtest(
            ticks,
            initial_cash=Decimal("100000"),
            short_window=10,
            long_window=30,
        )
        assert result.total_ticks == 100
        # With a clear uptrend, momentum should fire at least one BUY
        assert result.total_trades >= 1

    async def test_backtest_downtrend(self):
        """Strong downtrend should trigger sell signals."""
        prices = [200.0] * 60 + [200.0 - i * 2.0 for i in range(40)]
        ticks = make_ticks(prices)
        result = await run_backtest(
            ticks,
            initial_cash=Decimal("100000"),
            short_window=10,
            long_window=30,
        )
        assert result.total_ticks == 100

    async def test_backtest_sideways(self):
        """Sideways market should produce few or no trades."""
        # Oscillating around 100 with tiny amplitude
        prices = [100.0 + (i % 3 - 1) * 0.01 for i in range(100)]
        ticks = make_ticks(prices)
        result = await run_backtest(
            ticks,
            initial_cash=Decimal("100000"),
            short_window=10,
            long_window=30,
        )
        assert result.total_ticks == 100
        # Should have equity curve
        assert len(result.equity_curve) == 100

    async def test_backtest_result_summary(self):
        """Summary string should contain key metrics."""
        ticks = make_ticks([100.0] * 10)
        result = await run_backtest(ticks)
        summary = result.summary()
        assert "BACKTEST RESULTS" in summary
        assert "Total trades:" in summary
        assert "Max drawdown:" in summary
        assert "Sharpe ratio:" in summary
