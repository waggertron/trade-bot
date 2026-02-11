from __future__ import annotations

import asyncio
import logging
import os

import httpx

from src.data.providers.base import Interval, OHLCBar, ProviderName

logger = logging.getLogger(__name__)

SUPPORTED_INTERVALS = {Interval.H1, Interval.D1}

_ENDPOINT_MAP: dict[Interval, str] = {
    Interval.D1: "https://min-api.cryptocompare.com/data/v2/histoday",
    Interval.H1: "https://min-api.cryptocompare.com/data/v2/histohour",
}

MAX_BARS_PER_PAGE = 2000


async def download(
    symbol: str,
    interval: Interval = Interval.D1,
    since: int | None = None,
    max_bars: int | None = None,
    api_key: str | None = None,
) -> list[OHLCBar]:
    """Download OHLC data from CryptoCompare with backward pagination via toTs."""
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"CryptoCompare does not support interval {interval.value}")

    # Parse symbol: "BTC/USD" -> fsym=BTC, tsym=USD
    parts = symbol.split("/")
    if len(parts) != 2:
        raise ValueError(f"Symbol must be in 'BASE/QUOTE' format, got: {symbol}")
    fsym, tsym = parts

    url = _ENDPOINT_MAP[interval]
    key = api_key or os.environ.get("CRYPTOCOMPARE_API_KEY")

    all_bars: list[OHLCBar] = []
    to_ts: int | None = None

    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            params: dict[str, str | int] = {
                "fsym": fsym,
                "tsym": tsym,
                "limit": MAX_BARS_PER_PAGE,
            }
            if to_ts is not None:
                params["toTs"] = to_ts
            if key:
                params["api_key"] = key

            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            if data.get("Response") == "Error":
                raise RuntimeError(f"CryptoCompare error: {data.get('Message', 'unknown')}")

            rows = data.get("Data", {}).get("Data", [])
            if not rows:
                break

            page_bars: list[OHLCBar] = []
            for row in rows:
                # Filter empty bars
                if float(row.get("close", 0)) == 0 and float(row.get("open", 0)) == 0:
                    continue
                page_bars.append(OHLCBar(
                    timestamp=int(row["time"]),
                    open=str(row["open"]),
                    high=str(row["high"]),
                    low=str(row["low"]),
                    close=str(row["close"]),
                    volume=str(row.get("volumefrom", 0)),
                    source=ProviderName.CRYPTOCOMPARE.value,
                ))

            if not page_bars:
                break

            all_bars = page_bars + all_bars  # prepend since we paginate backward

            logger.info(
                "CryptoCompare: fetched %d bars (total: %d)", len(page_bars), len(all_bars)
            )

            if max_bars and len(all_bars) >= max_bars:
                all_bars = all_bars[-max_bars:]
                break

            # Stop if we've gone back far enough
            if since and page_bars[0].timestamp <= since:
                all_bars = [b for b in all_bars if b.timestamp >= since]
                break

            # If fewer bars than limit, we've reached the beginning
            if len(rows) < MAX_BARS_PER_PAGE:
                break

            # Paginate backward: use earliest timestamp as new toTs
            to_ts = page_bars[0].timestamp - 1

            await asyncio.sleep(0.3)

    return all_bars
