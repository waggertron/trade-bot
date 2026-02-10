# tests/test_execution.py
import pytest
from datetime import datetime, timezone
from decimal import Decimal

from src.agents.execution import PaperExecutionAgent
from src.core.models import AssetType, Order, OrderSide, OrderType


@pytest.fixture
def executor():
    return PaperExecutionAgent(slippage_pct=Decimal("0.1"))


async def test_submit_market_order(executor):
    executor.set_current_price("AAPL", Decimal("150.00"))
    order = Order(
        symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.MARKET,
        quantity=Decimal("10"), asset_type=AssetType.STOCK,
    )
    fill = await executor.submit_order(order)
    assert fill.symbol == "AAPL"
    assert fill.quantity == Decimal("10")
    # Slippage: buy at 150 + 0.1% = 150.15
    assert fill.fill_price == Decimal("150.15")


async def test_submit_limit_order_fills(executor):
    executor.set_current_price("AAPL", Decimal("149.00"))
    order = Order(
        symbol="AAPL", side=OrderSide.BUY, order_type=OrderType.LIMIT,
        quantity=Decimal("10"), limit_price=Decimal("150.00"),
        asset_type=AssetType.STOCK,
    )
    fill = await executor.submit_order(order)
    assert fill.fill_price == Decimal("149.00")  # Fills at current price (better than limit)


async def test_cancel_order(executor):
    result = await executor.cancel_order("nonexistent")
    assert result is True  # Paper mode always succeeds


async def test_cancel_all(executor):
    count = await executor.cancel_all()
    assert count == 0
