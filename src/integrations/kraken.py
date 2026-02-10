from __future__ import annotations

from decimal import Decimal

import httpx


class KrakenFeed:
    """Wrapper around Kraken REST API for crypto market data."""

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self._api_key = api_key
        self._api_secret = api_secret
        self._client = httpx.AsyncClient(
            base_url="https://api.kraken.com",
            timeout=10.0,
        )

    async def connect(self) -> None:
        pass  # REST-based, no persistent connection needed

    async def disconnect(self) -> None:
        await self._client.aclose()

    async def get_price(self, symbol: str) -> Decimal:
        pair = symbol.replace("/", "")
        resp = await self._client.get(f"/0/public/Ticker?pair={pair}")
        resp.raise_for_status()
        data = resp.json()
        result = data["result"]
        pair_data = next(iter(result.values()))
        return Decimal(pair_data["c"][0])  # Last trade close price

    async def get_order_book(self, symbol: str) -> dict:
        pair = symbol.replace("/", "")
        resp = await self._client.get(f"/0/public/Depth?pair={pair}&count=10")
        resp.raise_for_status()
        data = resp.json()
        result = next(iter(data["result"].values()))
        return {
            "bids": [(b[0], b[1]) for b in result["bids"]],
            "asks": [(a[0], a[1]) for a in result["asks"]],
        }
