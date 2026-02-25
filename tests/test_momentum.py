from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.agents.strategies.momentum import MomentumStrategy
from src.core.models import AssetType, MarketTick, SignalDirection


def make_ticks(prices: list[float], symbol="AAPL") -> list[MarketTick]:
    """Create a series of ticks from price list (oldest first)."""
    now = datetime.now(UTC)
    return [
        MarketTick(
            symbol=symbol,
            price=Decimal(str(p)),
            volume=1000,
            timestamp=now - timedelta(minutes=len(prices) - i),
            asset_type=AssetType.STOCK,
        )
        for i, p in enumerate(prices)
    ]


@pytest.fixture
def strategy():
    return MomentumStrategy(short_window=5, long_window=10)


async def test_buy_signal_on_uptrend(strategy):
    # Prices trending up: short MA > long MA
    prices = [100, 101, 102, 101, 103, 104, 106, 108, 110, 112, 115, 118, 120]
    ticks = make_ticks(prices)
    signal = await strategy.evaluate("AAPL", ticks)
    assert signal is not None
    assert signal.direction == SignalDirection.BUY
    assert signal.strategy_name == "momentum"


async def test_sell_signal_on_downtrend(strategy):
    # Prices trending down: short MA < long MA
    prices = [120, 118, 115, 112, 110, 108, 106, 104, 102, 101, 99, 97, 95]
    ticks = make_ticks(prices)
    signal = await strategy.evaluate("AAPL", ticks)
    assert signal is not None
    assert signal.direction == SignalDirection.SELL


async def test_no_signal_insufficient_data(strategy):
    prices = [100, 101, 102]
    ticks = make_ticks(prices)
    signal = await strategy.evaluate("AAPL", ticks)
    assert signal is None


async def test_has_name(strategy):
    assert strategy.name == "momentum"
