"""Tests for RegimeTagger: regime labeling and per-regime performance stats."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.analytics.models import AttributedFill
from src.analytics.regime_tagger import RegimeTagger
from src.core.models import Fill, OrderSide

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def make_fill(
    symbol: str = "BTC/USD",
    side: OrderSide = OrderSide.BUY,
    price: float = 100.0,
    qty: float = 1.0,
    ts: datetime | None = None,
    fill_id: str | None = None,
) -> Fill:
    f = Fill(
        order_id="test",
        symbol=symbol,
        side=side,
        quantity=Decimal(str(qty)),
        fill_price=Decimal(str(price)),
        timestamp=ts or datetime.now(UTC),
    )
    if fill_id is not None:
        # Override the auto-generated id
        object.__setattr__(f, "id", fill_id)
    return f


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSetAndGetRegime:
    def test_set_and_get_regime(self) -> None:
        tagger = RegimeTagger()
        tagger.set_regime("BTC/USD", 1700000000, "high_vol")
        assert tagger.get_regime("BTC/USD", 1700000000) == "high_vol"

    def test_get_regime_unknown(self) -> None:
        tagger = RegimeTagger()
        assert tagger.get_regime("BTC/USD", 1700000000) == "unknown"


class TestTagFills:
    def test_tag_fills_with_regime(self) -> None:
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        ts_unix = int(ts.timestamp())

        tagger = RegimeTagger()
        tagger.set_regime("BTC/USD", ts_unix, "low_vol")

        fill = make_fill(symbol="BTC/USD", ts=ts)
        result = tagger.tag_fills([fill])

        assert len(result) == 1
        assert result[0].regime == "low_vol"
        assert result[0].fill == fill

    def test_tag_fills_with_strategy_map(self) -> None:
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        ts_unix = int(ts.timestamp())

        tagger = RegimeTagger()
        tagger.set_regime("BTC/USD", ts_unix, "high_vol")

        fill = make_fill(symbol="BTC/USD", ts=ts, fill_id="fill-1")
        strategy_map = {"fill-1": "momentum"}

        result = tagger.tag_fills([fill], strategy_map=strategy_map)

        assert len(result) == 1
        assert result[0].strategy == "momentum"
        assert result[0].regime == "high_vol"

    def test_tag_fills_no_strategy_map(self) -> None:
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        fill = make_fill(symbol="BTC/USD", ts=ts)

        tagger = RegimeTagger()
        result = tagger.tag_fills([fill])

        assert len(result) == 1
        assert result[0].strategy == ""

    def test_tag_fills_unknown_regime(self) -> None:
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        fill = make_fill(symbol="BTC/USD", ts=ts)

        tagger = RegimeTagger()
        # Do NOT set any regime
        result = tagger.tag_fills([fill])

        assert len(result) == 1
        assert result[0].regime == "unknown"


class TestPerformanceByRegime:
    def test_performance_by_regime(self) -> None:
        ts_low = datetime(2024, 1, 1, tzinfo=UTC)
        ts_high = datetime(2024, 6, 1, tzinfo=UTC)

        # Create buy/sell pairs for two regimes
        buy_low = make_fill(side=OrderSide.BUY, price=100.0, qty=1.0, ts=ts_low)
        sell_low = make_fill(side=OrderSide.SELL, price=110.0, qty=1.0, ts=ts_low)
        buy_high = make_fill(side=OrderSide.BUY, price=200.0, qty=1.0, ts=ts_high)
        sell_high = make_fill(side=OrderSide.SELL, price=190.0, qty=1.0, ts=ts_high)

        attributed = [
            AttributedFill(fill=buy_low, strategy="", regime="low"),
            AttributedFill(fill=sell_low, strategy="", regime="low"),
            AttributedFill(fill=buy_high, strategy="", regime="high"),
            AttributedFill(fill=sell_high, strategy="", regime="high"),
        ]

        tagger = RegimeTagger()
        stats = tagger.performance_by_regime(attributed)

        assert "low" in stats
        assert "high" in stats
        assert stats["low"].total_trades == 1
        assert stats["low"].total_pnl == pytest.approx(10.0)
        assert stats["high"].total_trades == 1
        assert stats["high"].total_pnl == pytest.approx(-10.0)

    def test_performance_by_regime_empty(self) -> None:
        tagger = RegimeTagger()
        stats = tagger.performance_by_regime([])
        assert stats == {}
