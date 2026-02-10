# src/agents/execution.py
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from src.core.models import Fill, Order, OrderSide, OrderType


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
            timestamp=datetime.now(timezone.utc),
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
