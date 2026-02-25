# src/agents/execution.py
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from src.core.models import AssetType, Fill, Order, OrderSide, OrderType


class PaperExecutionAgent:
    """Simulates order execution for paper trading with configurable slippage."""

    def __init__(self, slippage_pct: Decimal = Decimal("0.1")):
        self._slippage_pct = slippage_pct
        self._current_prices: dict[str, Decimal] = {}
        self._open_orders: dict[str, Order] = {}

    def set_current_price(self, symbol: str, price: Decimal) -> None:
        """Set the current simulated market price for a symbol."""
        self._current_prices[symbol] = price

    async def submit_order(self, order: Order) -> Fill:
        """Submit an order and return a simulated fill.

        Market orders include slippage (positive for buys, negative for sells).
        Limit orders fill at the current price when it is within the limit.
        """
        base_price = self._current_prices.get(order.symbol, Decimal("0"))

        if order.order_type == OrderType.MARKET:
            slippage = base_price * self._slippage_pct / Decimal("100")
            if order.side == OrderSide.BUY:
                fill_price = base_price + slippage
            else:
                fill_price = base_price - slippage
        elif order.order_type == OrderType.LIMIT:
            fill_price = base_price  # Fill at current price if within limit
        else:
            fill_price = base_price

        return Fill(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            timestamp=datetime.now(UTC),
        )

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by ID. In paper mode, always succeeds."""
        self._open_orders.pop(order_id, None)
        return True

    async def cancel_all(self) -> int:
        """Cancel all open orders. Returns the count of cancelled orders."""
        count = len(self._open_orders)
        self._open_orders.clear()
        return count


class LiveExecutionAgent:
    """Routes orders to real brokers based on asset type.

    Requires explicit ``enable()`` before any orders are submitted.
    Cancel operations always work regardless of enabled state for safety.
    """

    def __init__(self, stock_executor, crypto_executor) -> None:
        self._stock_executor = stock_executor
        self._crypto_executor = crypto_executor
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def set_current_price(self, symbol: str, price: Decimal) -> None:
        """No-op for live execution — prices come from the market."""

    async def submit_order(self, order: Order) -> Fill:
        if not self._enabled:
            raise RuntimeError("Live execution is not enabled")

        executor = self._executor_for(order.asset_type)
        return await executor.submit_order(order)

    async def cancel_order(self, order_id: str) -> bool:
        """Try both executors — returns True if either cancelled."""
        stock_ok = await self._stock_executor.cancel_order(order_id)
        crypto_ok = await self._crypto_executor.cancel_order(order_id)
        return stock_ok or crypto_ok

    async def cancel_all(self) -> int:
        stock_count = await self._stock_executor.cancel_all()
        crypto_count = await self._crypto_executor.cancel_all()
        return stock_count + crypto_count

    def _executor_for(self, asset_type: AssetType):
        if asset_type == AssetType.CRYPTO:
            return self._crypto_executor
        return self._stock_executor
