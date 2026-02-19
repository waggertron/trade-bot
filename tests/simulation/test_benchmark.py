"""Tests for the BenchmarkSimulator."""
from __future__ import annotations

import pytest

from src.data.providers.base import OHLCBar
from src.simulation.benchmark import BenchmarkSimulator


def _make_bars(n: int, start_price: float = 100.0, trend: float = 0.5) -> list[OHLCBar]:
    """Create n daily bars with configurable trend per day."""
    bars = []
    base_ts = 1700000000
    for i in range(n):
        price = start_price + i * trend
        bars.append(OHLCBar(
            timestamp=base_ts + i * 86400,
            open=str(price - 0.2),
            high=str(price + 1.0),
            low=str(price - 1.0),
            close=str(price),
            volume=str(1_000_000),
            source="test",
        ))
    return bars


class TestBuyAndHold:
    def test_uptrend_positive_return(self):
        bars = _make_bars(60, start_price=100.0, trend=0.5)
        bench = BenchmarkSimulator()
        result = bench.buy_and_hold(bars, initial_balance=10_000.0)

        assert result.name == "SPY Buy-and-Hold"
        assert result.initial_balance == 10_000.0
        assert result.final_value > result.initial_balance
        assert result.return_pct > 0
        assert len(result.equity_curve) == 60

    def test_downtrend_negative_return(self):
        bars = _make_bars(60, start_price=100.0, trend=-0.5)
        bench = BenchmarkSimulator()
        result = bench.buy_and_hold(bars, initial_balance=10_000.0)

        assert result.return_pct < 0
        assert result.final_value < result.initial_balance

    def test_flat_market_zero_return(self):
        bars = _make_bars(60, start_price=100.0, trend=0.0)
        bench = BenchmarkSimulator()
        result = bench.buy_and_hold(bars, initial_balance=10_000.0)

        assert abs(result.return_pct) < 0.01
        assert result.max_drawdown == 0.0

    def test_max_drawdown_positive(self):
        # Create a V-shaped price: up, then down, then up
        bars = []
        base_ts = 1700000000
        prices = [100, 110, 120, 105, 90, 95, 115]
        for i, p in enumerate(prices):
            bars.append(OHLCBar(
                timestamp=base_ts + i * 86400,
                open=str(p), high=str(p + 1), low=str(p - 1),
                close=str(p), volume="1000000", source="test",
            ))
        bench = BenchmarkSimulator()
        result = bench.buy_and_hold(bars, initial_balance=10_000.0)

        # Drawdown should be from peak 120 to trough 90 = 25%
        assert result.max_drawdown > 20.0

    def test_equity_curve_tracks_price(self):
        bars = _make_bars(5, start_price=100.0, trend=10.0)
        bench = BenchmarkSimulator()
        result = bench.buy_and_hold(bars, initial_balance=10_000.0)

        # First value should be initial_balance
        assert result.equity_curve[0] == pytest.approx(10_000.0)
        # Last bar close = 100 + 4*10 = 140, so value = 10000 * 140/100 = 14000
        assert result.equity_curve[-1] == pytest.approx(14_000.0)


class TestMonthlyDCA:
    def test_uptrend_positive_return(self):
        # 60 trading days ~ 3 months
        bars = _make_bars(60, start_price=100.0, trend=0.5)
        bench = BenchmarkSimulator()
        result = bench.monthly_dca(bars, initial_balance=10_000.0)

        assert result.name == "SPY Monthly DCA"
        assert result.initial_balance == 10_000.0
        assert result.final_value > 0
        assert len(result.equity_curve) == 60

    def test_dca_vs_lump_sum_in_steady_uptrend(self):
        # In a steady uptrend, lump sum should beat DCA
        bars = _make_bars(60, start_price=100.0, trend=0.5)
        bench = BenchmarkSimulator()
        bh = bench.buy_and_hold(bars, initial_balance=10_000.0)
        dca = bench.monthly_dca(bars, initial_balance=10_000.0)

        # Buy-and-hold should outperform DCA in uptrend
        assert bh.return_pct > dca.return_pct

    def test_short_period_single_buy(self):
        # Less than 21 trading days = 1 month, should still work
        bars = _make_bars(10, start_price=100.0, trend=1.0)
        bench = BenchmarkSimulator()
        result = bench.monthly_dca(bars, initial_balance=10_000.0)

        assert result.final_value > 0
        assert len(result.equity_curve) == 10

    def test_sharpe_ratio_computed(self):
        bars = _make_bars(60, start_price=100.0, trend=0.5)
        bench = BenchmarkSimulator()
        result = bench.monthly_dca(bars, initial_balance=10_000.0)

        # Should produce a finite Sharpe ratio
        assert result.sharpe_ratio != 0.0

    def test_empty_bars_raises(self):
        bench = BenchmarkSimulator()
        with pytest.raises(ValueError):
            bench.buy_and_hold([], initial_balance=10_000.0)
        with pytest.raises(ValueError):
            bench.monthly_dca([], initial_balance=10_000.0)
