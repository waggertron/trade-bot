"""Tests for persisting trade fills to the database."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.core.models import Fill, OrderSide
from src.db.database import Database
from src.db.models import TradeRecord


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_fill_is_persisted(db):
    fill = Fill(
        order_id="order-1",
        symbol="BTC/USD",
        side=OrderSide.BUY,
        quantity=Decimal("0.5"),
        fill_price=Decimal("50000"),
        timestamp=datetime.now(timezone.utc),
    )
    record = TradeRecord(
        symbol=fill.symbol,
        side=fill.side.value,
        quantity=str(fill.quantity),
        price=str(fill.fill_price),
        commission=str(fill.commission),
        strategy="momentum",
        paper=True,
        timestamp=fill.timestamp,
    )
    trade_id = await db.save_trade(record)
    trades = await db.list_trades()
    assert len(trades) == 1
    assert trades[0].symbol == "BTC/USD"
    assert trades[0].side == "buy"
    assert trades[0].price == "50000"


@pytest.mark.asyncio
async def test_persist_fill_helper_saves_to_db(db):
    """Test the persist_fill helper function used in main.py's trading loop."""
    from main import persist_fill

    fill = Fill(
        order_id="order-2",
        symbol="ETH/USD",
        side=OrderSide.SELL,
        quantity=Decimal("1.5"),
        fill_price=Decimal("3000"),
        timestamp=datetime.now(timezone.utc),
        commission=Decimal("0.15"),
    )
    await persist_fill(db, fill, strategy_name="sentiment", is_paper=True)
    trades = await db.list_trades()
    assert len(trades) == 1
    assert trades[0].symbol == "ETH/USD"
    assert trades[0].side == "sell"
    assert trades[0].strategy == "sentiment"
    assert trades[0].commission == "0.15"


@pytest.mark.asyncio
async def test_persist_fill_does_not_raise_on_db_error(db):
    """Persistence failures should be caught, not crash the loop."""
    from main import persist_fill

    await db.close()  # Force DB error

    fill = Fill(
        order_id="order-3",
        symbol="BTC/USD",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        fill_price=Decimal("60000"),
        timestamp=datetime.now(timezone.utc),
    )
    # Should not raise
    await persist_fill(db, fill, strategy_name="momentum", is_paper=True)
