from __future__ import annotations

import asyncio
import logging

import httpx

from src.data.providers.base import Interval, OHLCBar, ProviderName

logger = logging.getLogger(__name__)

SUPPORTED_INTERVALS = {
    Interval.M1, Interval.M5, Interval.M15, Interval.M30,
    Interval.H1, Interval.H4, Interval.D1, Interval.W1,
}

_INTERVAL_MAP: dict[Interval, str] = {
    Interval.M1: "1m",
    Interval.M5: "5m",
    Interval.M15: "15m",
    Interval.M30: "30m",
    Interval.H1: "1h",
    Interval.H4: "4h",
    Interval.D1: "1d",
    Interval.W1: "1w",
}

BASE_URL = "https://api.binance.us/api/v3/klines"
MAX_BARS_PER_PAGE = 1000


async def download(
    symbol: str,
    interval: Interval = Interval.D1,
    since: int | None = None,
    max_bars: int | None = None,
) -> list[OHLCBar]:
    """Download OHLC data from Binance.US with forward pagination via startTime."""
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"Binance does not support interval {interval.value}")

    # "BTC/USD" -> "BTCUSD"
    binance_symbol = symbol.replace("/", "")
    binance_interval = _INTERVAL_MAP[interval]
    all_bars: list[OHLCBar] = []

    # Binance uses millisecond timestamps
    start_time_ms: int | None = since * 1000 if since else None

    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            params: dict[str, str | int] = {
                "symbol": binance_symbol,
                "interval": binance_interval,
                "limit": MAX_BARS_PER_PAGE,
            }
            if start_time_ms is not None:
                params["startTime"] = start_time_ms

            resp = await client.get(BASE_URL, params=params)
            resp.raise_for_status()
            rows = resp.json()

            if not rows:
                break

            for row in rows:
                # Binance kline: [openTime, open, high, low, close, volume,
                #                  closeTime, quoteVolume, trades, ...]
                all_bars.append(OHLCBar(
                    timestamp=int(row[0]) // 1000,  # ms -> seconds
                    open=str(row[1]),
                    high=str(row[2]),
                    low=str(row[3]),
                    close=str(row[4]),
                    volume=str(row[5]),
                    source=ProviderName.BINANCE.value,
                ))

            logger.info("Binance: fetched %d bars (total: %d)", len(rows), len(all_bars))

            if max_bars and len(all_bars) >= max_bars:
                all_bars = all_bars[:max_bars]
                break

            if len(rows) < MAX_BARS_PER_PAGE:
                break

            # Forward paginate: next page starts after last bar's close time
            start_time_ms = int(rows[-1][6]) + 1  # closeTime + 1ms

            await asyncio.sleep(0.2)

    return all_bars
