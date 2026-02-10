import pytest
from datetime import datetime, timezone
from decimal import Decimal

from src.db.database import Database
from src.db.models import TradeRecord, SignalRecord


@pytest.fixture
async def db(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await database.initialize()
    yield database
    await database.close()


async def test_save_and_get_trade(db):
    trade = TradeRecord(
        symbol="AAPL",
        side="buy",
        quantity="10",
        price="150.25",
        commission="1.00",
        strategy="momentum",
        paper=True,
        timestamp=datetime.now(timezone.utc),
    )
    trade_id = await db.save_trade(trade)
    assert trade_id is not None
    retrieved = await db.get_trade(trade_id)
    assert retrieved.symbol == "AAPL"
    assert retrieved.side == "buy"


async def test_save_and_list_signals(db):
    signal = SignalRecord(
        symbol="AAPL",
        direction="buy",
        confidence=0.85,
        strategy="momentum",
        reasoning="Strong trend",
        timestamp=datetime.now(timezone.utc),
    )
    await db.save_signal(signal)
    signals = await db.list_signals(limit=10)
    assert len(signals) == 1
    assert signals[0].symbol == "AAPL"


async def test_list_trades_by_strategy(db):
    for symbol in ["AAPL", "MSFT"]:
        await db.save_trade(TradeRecord(
            symbol=symbol, side="buy", quantity="10", price="100",
            commission="1", strategy="momentum", paper=True,
            timestamp=datetime.now(timezone.utc),
        ))
    await db.save_trade(TradeRecord(
        symbol="GOOGL", side="buy", quantity="5", price="200",
        commission="1", strategy="sentiment", paper=True,
        timestamp=datetime.now(timezone.utc),
    ))
    momentum_trades = await db.list_trades(strategy="momentum")
    assert len(momentum_trades) == 2
    all_trades = await db.list_trades()
    assert len(all_trades) == 3
