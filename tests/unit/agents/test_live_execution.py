"""Tests for LiveExecutionAgent that routes orders to real brokers."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.agents.execution import LiveExecutionAgent
from src.core.models import AssetType, Fill, Order, OrderSide, OrderType


@pytest.fixture
def mock_ibkr_executor():
    executor = AsyncMock()
    executor.submit_order.return_value = Fill(
        order_id="ibkr-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=Decimal("10"),
        fill_price=Decimal("175.50"),
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        commission=Decimal("1.00"),
    )
    executor.cancel_order.return_value = True
    executor.cancel_all.return_value = 0
    return executor


@pytest.fixture
def mock_kraken_executor():
    executor = AsyncMock()
    executor.submit_order.return_value = Fill(
        order_id="kraken-1",
        symbol="BTC/USD",
        side=OrderSide.BUY,
        quantity=Decimal("0.5"),
        fill_price=Decimal("50000"),
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        commission=Decimal("5.00"),
    )
    executor.cancel_order.return_value = True
    executor.cancel_all.return_value = 0
    return executor


@pytest.fixture
def live_agent(mock_ibkr_executor, mock_kraken_executor):
    agent = LiveExecutionAgent(
        stock_executor=mock_ibkr_executor,
        crypto_executor=mock_kraken_executor,
    )
    agent.enable()
    return agent


class TestLiveExecutionRouting:
    async def test_routes_stock_orders_to_ibkr(self, live_agent, mock_ibkr_executor):
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("10"),
            asset_type=AssetType.STOCK,
        )

        fill = await live_agent.submit_order(order)

        mock_ibkr_executor.submit_order.assert_called_once_with(order)
        assert fill.symbol == "AAPL"
        assert fill.fill_price == Decimal("175.50")

    async def test_routes_crypto_orders_to_kraken(self, live_agent, mock_kraken_executor):
        order = Order(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.5"),
            asset_type=AssetType.CRYPTO,
        )

        fill = await live_agent.submit_order(order)

        mock_kraken_executor.submit_order.assert_called_once_with(order)
        assert fill.symbol == "BTC/USD"
        assert fill.fill_price == Decimal("50000")

    async def test_cancel_order_delegates_to_both(
        self,
        live_agent,
        mock_ibkr_executor,
        mock_kraken_executor,
    ):
        mock_ibkr_executor.cancel_order.return_value = False
        mock_kraken_executor.cancel_order.return_value = True

        result = await live_agent.cancel_order("some-id")

        assert result is True
        mock_ibkr_executor.cancel_order.assert_called_once_with("some-id")
        mock_kraken_executor.cancel_order.assert_called_once_with("some-id")

    async def test_cancel_all_delegates_to_both(
        self,
        live_agent,
        mock_ibkr_executor,
        mock_kraken_executor,
    ):
        mock_ibkr_executor.cancel_all.return_value = 2
        mock_kraken_executor.cancel_all.return_value = 3

        count = await live_agent.cancel_all()

        assert count == 5

    async def test_set_current_price_is_noop(self, live_agent):
        """LiveExecutionAgent doesn't track simulated prices."""
        live_agent.set_current_price("BTC/USD", Decimal("50000"))


class TestLiveExecutionSafety:
    async def test_rejects_order_when_not_enabled(self):
        """Live execution requires explicit enable call."""
        agent = LiveExecutionAgent(
            stock_executor=AsyncMock(),
            crypto_executor=AsyncMock(),
        )

        order = Order(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.5"),
            asset_type=AssetType.CRYPTO,
        )

        with pytest.raises(RuntimeError, match="not enabled"):
            await agent.submit_order(order)

    async def test_enable_allows_execution(self):
        mock_executor = AsyncMock()
        mock_executor.submit_order.return_value = Fill(
            order_id="o1",
            symbol="BTC/USD",
            side=OrderSide.BUY,
            quantity=Decimal("0.5"),
            fill_price=Decimal("50000"),
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        )

        agent = LiveExecutionAgent(
            stock_executor=AsyncMock(),
            crypto_executor=mock_executor,
        )
        agent.enable()

        order = Order(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.5"),
            asset_type=AssetType.CRYPTO,
        )

        fill = await agent.submit_order(order)
        assert fill.symbol == "BTC/USD"

    async def test_disable_blocks_execution(self):
        agent = LiveExecutionAgent(
            stock_executor=AsyncMock(),
            crypto_executor=AsyncMock(),
        )
        agent.enable()
        agent.disable()

        order = Order(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.5"),
            asset_type=AssetType.CRYPTO,
        )

        with pytest.raises(RuntimeError, match="not enabled"):
            await agent.submit_order(order)

    async def test_cancel_works_even_when_disabled(self):
        """Cancel should always work for safety."""
        mock_ibkr = AsyncMock()
        mock_ibkr.cancel_all.return_value = 1
        mock_kraken = AsyncMock()
        mock_kraken.cancel_all.return_value = 2

        agent = LiveExecutionAgent(
            stock_executor=mock_ibkr,
            crypto_executor=mock_kraken,
        )

        count = await agent.cancel_all()
        assert count == 3
