import pytest
from datetime import datetime, timezone
from decimal import Decimal

from src.agents.market_data import MarketDataManager
from src.core.models import AssetType, MarketTick


class MockStockFeed:
    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def get_price(self, symbol):
        return Decimal("150.25")

    async def get_order_book(self, symbol):
        return {"bids": [("150.00", "100")], "asks": [("150.50", "100")]}


class MockCryptoFeed:
    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def get_price(self, symbol):
        return Decimal("45000.50")

    async def get_order_book(self, symbol):
        return {"bids": [("45000", "1")], "asks": [("45001", "1")]}


@pytest.fixture
def market_data():
    return MarketDataManager(
        stock_feed=MockStockFeed(),
        crypto_feed=MockCryptoFeed(),
        stock_symbols=["AAPL"],
        crypto_symbols=["BTC/USD"],
    )


async def test_connect(market_data):
    await market_data.connect()  # Should not raise


async def test_get_order_book_stock(market_data):
    book = await market_data.get_order_book("AAPL")
    assert "bids" in book
    assert "asks" in book


async def test_get_order_book_crypto(market_data):
    book = await market_data.get_order_book("BTC/USD")
    assert "bids" in book


async def test_snapshot_prices(market_data):
    await market_data.connect()
    ticks = await market_data.snapshot()
    symbols = {t.symbol for t in ticks}
    assert "AAPL" in symbols
    assert "BTC/USD" in symbols
