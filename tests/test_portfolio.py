from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.agents.portfolio import PortfolioManager
from src.core.models import Fill, OrderSide


@pytest.fixture
def portfolio():
    return PortfolioManager(initial_cash=Decimal("100000"))


async def test_initial_snapshot(portfolio):
    snapshot = await portfolio.get_snapshot()
    assert snapshot.cash == Decimal("100000")
    assert snapshot.positions == []
    assert snapshot.total_value == Decimal("100000")


async def test_record_buy_fill(portfolio):
    fill = Fill(
        order_id="ord-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        fill_price=Decimal("150"),
        timestamp=datetime.now(UTC),
        commission=Decimal("1"),
    )
    await portfolio.record_fill(fill)
    positions = await portfolio.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "AAPL"
    assert positions[0].quantity == Decimal("10")
    assert positions[0].avg_entry_price == Decimal("150")

    snapshot = await portfolio.get_snapshot()
    assert snapshot.cash == Decimal("98499")  # 100000 - 1500 - 1


async def test_record_sell_fill(portfolio):
    buy = Fill(
        order_id="ord-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        fill_price=Decimal("150"),
        timestamp=datetime.now(UTC),
        commission=Decimal("1"),
    )
    await portfolio.record_fill(buy)

    sell = Fill(
        order_id="ord-2",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=Decimal("5"),
        fill_price=Decimal("160"),
        timestamp=datetime.now(UTC),
        commission=Decimal("1"),
    )
    await portfolio.record_fill(sell)

    positions = await portfolio.get_positions()
    assert len(positions) == 1
    assert positions[0].quantity == Decimal("5")

    snapshot = await portfolio.get_snapshot()
    # 100000 - 1500 - 1 + 800 - 1 = 99298
    assert snapshot.cash == Decimal("99298")


async def test_sell_all_removes_position(portfolio):
    buy = Fill(
        order_id="ord-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        fill_price=Decimal("150"),
        timestamp=datetime.now(UTC),
    )
    await portfolio.record_fill(buy)

    sell = Fill(
        order_id="ord-2",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=Decimal("10"),
        fill_price=Decimal("155"),
        timestamp=datetime.now(UTC),
    )
    await portfolio.record_fill(sell)

    positions = await portfolio.get_positions()
    assert len(positions) == 0


async def test_get_pnl(portfolio):
    buy = Fill(
        order_id="ord-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        fill_price=Decimal("150"),
        timestamp=datetime.now(UTC),
    )
    sell = Fill(
        order_id="ord-2",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=Decimal("10"),
        fill_price=Decimal("160"),
        timestamp=datetime.now(UTC),
    )
    await portfolio.record_fill(buy)
    await portfolio.record_fill(sell)
    pnl = await portfolio.get_pnl("day")
    assert pnl == 100.0  # (160-150)*10 = 100
