"""Tests for StrategyAttribution: FIFO fill pairing and per-strategy stats."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.analytics.attribution import StrategyAttribution
from src.analytics.models import AttributedFill, AttributionReport, StrategyStats, Trade
from src.core.models import Fill, OrderSide


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_fill(
    symbol: str = "BTC/USD",
    side: OrderSide = OrderSide.BUY,
    price: float = 100.0,
    qty: float = 1.0,
) -> Fill:
    return Fill(
        order_id="test",
        symbol=symbol,
        side=side,
        quantity=Decimal(str(qty)),
        fill_price=Decimal(str(price)),
        timestamp=datetime.now(timezone.utc),
    )


def make_attributed(
    fill: Fill,
    strategy: str = "momentum",
    regime: str = "medium",
) -> AttributedFill:
    return AttributedFill(fill=fill, strategy=strategy, regime=regime)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStrategyAttribution:
    """Tests for StrategyAttribution.analyze()."""

    def setup_method(self) -> None:
        self.attr = StrategyAttribution()

    # -- empty input --------------------------------------------------------

    def test_empty_fills(self) -> None:
        report = self.attr.analyze([])
        assert report.strategies == {}
        assert report.total_pnl == 0.0
        assert report.best_strategy == ""
        assert report.worst_strategy == ""

    # -- single strategy: win -----------------------------------------------

    def test_single_strategy_win(self) -> None:
        fills = [
            make_attributed(make_fill(side=OrderSide.BUY, price=100.0)),
            make_attributed(make_fill(side=OrderSide.SELL, price=110.0)),
        ]
        report = self.attr.analyze(fills)

        stats = report.strategies["momentum"]
        assert stats.total_trades == 1
        assert stats.total_pnl == pytest.approx(10.0)
        assert stats.win_rate == pytest.approx(1.0)
        assert stats.avg_win == pytest.approx(10.0)
        assert stats.avg_loss == 0.0

    # -- single strategy: loss ----------------------------------------------

    def test_single_strategy_loss(self) -> None:
        fills = [
            make_attributed(make_fill(side=OrderSide.BUY, price=100.0)),
            make_attributed(make_fill(side=OrderSide.SELL, price=90.0)),
        ]
        report = self.attr.analyze(fills)

        stats = report.strategies["momentum"]
        assert stats.total_trades == 1
        assert stats.total_pnl == pytest.approx(-10.0)
        assert stats.win_rate == pytest.approx(0.0)
        assert stats.avg_loss == pytest.approx(-10.0)
        assert stats.avg_win == 0.0

    # -- mixed wins and losses ----------------------------------------------

    def test_mixed_wins_and_losses(self) -> None:
        fills = [
            # Trade 1: buy 100, sell 120 -> +20
            make_attributed(make_fill(side=OrderSide.BUY, price=100.0)),
            make_attributed(make_fill(side=OrderSide.SELL, price=120.0)),
            # Trade 2: buy 100, sell 80 -> -20
            make_attributed(make_fill(side=OrderSide.BUY, price=100.0)),
            make_attributed(make_fill(side=OrderSide.SELL, price=80.0)),
            # Trade 3: buy 100, sell 115 -> +15
            make_attributed(make_fill(side=OrderSide.BUY, price=100.0)),
            make_attributed(make_fill(side=OrderSide.SELL, price=115.0)),
        ]
        report = self.attr.analyze(fills)

        stats = report.strategies["momentum"]
        assert stats.total_trades == 3
        assert stats.win_rate == pytest.approx(2.0 / 3.0)
        assert stats.total_pnl == pytest.approx(15.0)  # 20 - 20 + 15
        assert stats.avg_win == pytest.approx(17.5)  # (20 + 15) / 2
        assert stats.avg_loss == pytest.approx(-20.0)

    # -- multiple strategies ------------------------------------------------

    def test_multiple_strategies(self) -> None:
        fills = [
            # momentum: buy 100, sell 130 -> +30
            make_attributed(
                make_fill(side=OrderSide.BUY, price=100.0), strategy="momentum"
            ),
            make_attributed(
                make_fill(side=OrderSide.SELL, price=130.0), strategy="momentum"
            ),
            # ml_ensemble: buy 200, sell 190 -> -10
            make_attributed(
                make_fill(side=OrderSide.BUY, price=200.0), strategy="ml_ensemble"
            ),
            make_attributed(
                make_fill(side=OrderSide.SELL, price=190.0), strategy="ml_ensemble"
            ),
        ]
        report = self.attr.analyze(fills)

        assert "momentum" in report.strategies
        assert "ml_ensemble" in report.strategies
        assert report.strategies["momentum"].total_pnl == pytest.approx(30.0)
        assert report.strategies["ml_ensemble"].total_pnl == pytest.approx(-10.0)
        assert report.total_pnl == pytest.approx(20.0)

    # -- profit factor ------------------------------------------------------

    def test_profit_factor(self) -> None:
        fills = [
            # Win: buy 100, sell 400 -> +300
            make_attributed(make_fill(side=OrderSide.BUY, price=100.0)),
            make_attributed(make_fill(side=OrderSide.SELL, price=400.0)),
            # Loss: buy 200, sell 100 -> -100
            make_attributed(make_fill(side=OrderSide.BUY, price=200.0)),
            make_attributed(make_fill(side=OrderSide.SELL, price=100.0)),
        ]
        report = self.attr.analyze(fills)

        stats = report.strategies["momentum"]
        assert stats.profit_factor == pytest.approx(3.0)

    # -- max consecutive losses ---------------------------------------------

    def test_max_consecutive_losses(self) -> None:
        # Sequence: L, L, W, L, L, L -> max consecutive losses = 3
        trade_results = [
            (100.0, 90.0),   # L: -10
            (100.0, 95.0),   # L: -5
            (100.0, 120.0),  # W: +20
            (100.0, 80.0),   # L: -20
            (100.0, 85.0),   # L: -15
            (100.0, 99.0),   # L: -1
        ]
        fills = []
        for buy_price, sell_price in trade_results:
            fills.append(make_attributed(make_fill(side=OrderSide.BUY, price=buy_price)))
            fills.append(make_attributed(make_fill(side=OrderSide.SELL, price=sell_price)))

        report = self.attr.analyze(fills)
        stats = report.strategies["momentum"]
        assert stats.max_consecutive_losses == 3

    # -- best / worst strategy ----------------------------------------------

    def test_best_worst_strategy(self) -> None:
        fills = [
            # Strategy A: +500
            make_attributed(
                make_fill(side=OrderSide.BUY, price=100.0), strategy="A"
            ),
            make_attributed(
                make_fill(side=OrderSide.SELL, price=600.0), strategy="A"
            ),
            # Strategy B: -200
            make_attributed(
                make_fill(side=OrderSide.BUY, price=300.0), strategy="B"
            ),
            make_attributed(
                make_fill(side=OrderSide.SELL, price=100.0), strategy="B"
            ),
        ]
        report = self.attr.analyze(fills)

        assert report.best_strategy == "A"
        assert report.worst_strategy == "B"
        assert report.total_pnl == pytest.approx(300.0)  # 500 - 200

    # -- unpaired buys ignored ----------------------------------------------

    def test_unpaired_buys_ignored(self) -> None:
        fills = [
            make_attributed(make_fill(side=OrderSide.BUY, price=100.0)),
            make_attributed(make_fill(side=OrderSide.BUY, price=200.0)),
        ]
        report = self.attr.analyze(fills)

        # No sells -> no trades -> empty stats for momentum
        # Strategy may or may not appear; either way total_pnl == 0
        assert report.total_pnl == 0.0
        if "momentum" in report.strategies:
            assert report.strategies["momentum"].total_trades == 0

    # -- FIFO pairing -------------------------------------------------------

    def test_fifo_pairing(self) -> None:
        fills = [
            # Buy 1 at 100, Buy 2 at 200
            make_attributed(make_fill(side=OrderSide.BUY, price=100.0)),
            make_attributed(make_fill(side=OrderSide.BUY, price=200.0)),
            # Sell 1 at 150, Sell 2 at 250
            make_attributed(make_fill(side=OrderSide.SELL, price=150.0)),
            make_attributed(make_fill(side=OrderSide.SELL, price=250.0)),
        ]
        report = self.attr.analyze(fills)

        stats = report.strategies["momentum"]
        assert stats.total_trades == 2
        # FIFO: first buy (100) matches first sell (150) -> +50
        # FIFO: second buy (200) matches second sell (250) -> +50
        assert stats.total_pnl == pytest.approx(100.0)
        assert stats.win_rate == pytest.approx(1.0)
