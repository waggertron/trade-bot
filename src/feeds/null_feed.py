"""Placeholder stock feed when IBKR is not connected."""

from __future__ import annotations

from decimal import Decimal


class NullStockFeed:
    """Returns zero prices and empty order books for all symbols."""

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def get_price(self, symbol: str) -> Decimal:
        return Decimal("0")

    async def get_order_book(self, symbol: str) -> dict:
        return {"bids": [], "asks": []}
