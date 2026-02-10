from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from src.core.models import AssetType, MarketTick


class MarketDataManager:
    def __init__(
        self,
        stock_feed,
        crypto_feed,
        stock_symbols: list[str],
        crypto_symbols: list[str],
    ):
        self._stock_feed = stock_feed
        self._crypto_feed = crypto_feed
        self._stock_symbols = stock_symbols
        self._crypto_symbols = crypto_symbols

    async def connect(self) -> None:
        await self._stock_feed.connect()
        await self._crypto_feed.connect()

    async def disconnect(self) -> None:
        await self._stock_feed.disconnect()
        await self._crypto_feed.disconnect()

    async def get_order_book(self, symbol: str) -> dict:
        if "/" in symbol:
            return await self._crypto_feed.get_order_book(symbol)
        return await self._stock_feed.get_order_book(symbol)

    async def snapshot(self) -> list[MarketTick]:
        tasks = []
        for symbol in self._stock_symbols:
            tasks.append(self._fetch_tick(symbol, self._stock_feed, AssetType.STOCK))
        for symbol in self._crypto_symbols:
            tasks.append(self._fetch_tick(symbol, self._crypto_feed, AssetType.CRYPTO))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, MarketTick)]

    async def _fetch_tick(self, symbol: str, feed, asset_type: AssetType) -> MarketTick:
        price = await feed.get_price(symbol)
        return MarketTick(
            symbol=symbol,
            price=price,
            volume=0,
            timestamp=datetime.now(timezone.utc),
            asset_type=asset_type,
        )
