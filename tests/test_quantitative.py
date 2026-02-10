import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from src.agents.strategies.quantitative import QuantitativeStrategy
from src.core.models import AssetType, MarketTick, SignalDirection


def make_ticks(prices, symbol="AAPL"):
    now = datetime.now(timezone.utc)
    return [
        MarketTick(
            symbol=symbol, price=Decimal(str(p)), volume=1000,
            timestamp=now - timedelta(minutes=len(prices) - i),
            asset_type=AssetType.STOCK,
        )
        for i, p in enumerate(prices)
    ]


@pytest.fixture
def strategy():
    return QuantitativeStrategy(lookback=10, z_threshold=1.5)


async def test_buy_signal_price_below_mean(strategy):
    # Price drops well below the mean -> mean reversion buy
    prices = [100, 101, 100, 99, 100, 101, 100, 99, 100, 101, 90]
    ticks = make_ticks(prices)
    signal = await strategy.evaluate("AAPL", ticks)
    assert signal is not None
    assert signal.direction == SignalDirection.BUY


async def test_sell_signal_price_above_mean(strategy):
    # Price spikes well above the mean -> mean reversion sell
    prices = [100, 101, 100, 99, 100, 101, 100, 99, 100, 101, 115]
    ticks = make_ticks(prices)
    signal = await strategy.evaluate("AAPL", ticks)
    assert signal is not None
    assert signal.direction == SignalDirection.SELL


async def test_no_signal_price_near_mean(strategy):
    prices = [100, 101, 100, 99, 100, 101, 100, 99, 100, 101, 100]
    ticks = make_ticks(prices)
    signal = await strategy.evaluate("AAPL", ticks)
    assert signal is None


async def test_insufficient_data(strategy):
    ticks = make_ticks([100, 101, 102])
    signal = await strategy.evaluate("AAPL", ticks)
    assert signal is None


async def test_has_name(strategy):
    assert strategy.name == "quantitative"
