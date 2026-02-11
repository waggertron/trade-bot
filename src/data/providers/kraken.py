from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from src.data.providers.base import Interval, OHLCBar, ProviderName

logger = logging.getLogger(__name__)

SUPPORTED_INTERVALS = {
    Interval.M1, Interval.M5, Interval.M15, Interval.M30,
    Interval.H1, Interval.H4, Interval.D1, Interval.W1,
}

_INTERVAL_MAP: dict[Interval, int] = {
    Interval.M1: 1,
    Interval.M5: 5,
    Interval.M15: 15,
    Interval.M30: 30,
    Interval.H1: 60,
    Interval.H4: 240,
    Interval.D1: 1440,
    Interval.W1: 10080,
}

BASE_URL = "https://api.kraken.com/0/public/OHLC"


async def download(
    symbol: str,
    interval: Interval = Interval.H1,
    since: int | None = None,
    max_bars: int | None = None,
) -> list[OHLCBar]:
    """Download OHLC data from Kraken's public API with pagination."""
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"Kraken does not support interval {interval.value}")

    pair = symbol.replace("/", "")
    kraken_interval = _INTERVAL_MAP[interval]
    all_bars: list[OHLCBar] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            params: dict[str, str | int] = {"pair": pair, "interval": kraken_interval}
            if since is not None:
                params["since"] = since

            resp = await client.get(BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            if data.get("error"):
                raise RuntimeError(f"Kraken API error: {data['error']}")

            result: dict[str, Any] = data["result"]
            last = result.pop("last", None)
            pair_data: list[Any] = next(iter(result.values()), [])

            if not pair_data:
                break

            for row in pair_data:
                # [time, open, high, low, close, vwap, volume, count]
                all_bars.append(OHLCBar(
                    timestamp=int(row[0]),
                    open=str(row[1]),
                    high=str(row[2]),
                    low=str(row[3]),
                    close=str(row[4]),
                    volume=str(row[6]),
                    source=ProviderName.KRAKEN.value,
                ))

            logger.info("Kraken: fetched %d bars (total: %d)", len(pair_data), len(all_bars))

            if max_bars and len(all_bars) >= max_bars:
                all_bars = all_bars[:max_bars]
                break

            if len(pair_data) < 720:
                break

            if last is not None:
                since = int(last)
            else:
                break

            await asyncio.sleep(1.0)

    return all_bars
