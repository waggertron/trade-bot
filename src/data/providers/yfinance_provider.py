from __future__ import annotations

import asyncio
import logging

from src.data.providers.base import Interval, OHLCBar, ProviderName

logger = logging.getLogger(__name__)

SUPPORTED_INTERVALS = {Interval.D1}


def _convert_symbol(symbol: str) -> str:
    """Convert 'BTC/USD' -> 'BTC-USD' for Yahoo Finance format."""
    return symbol.replace("/", "-")


def _download_sync(
    symbol: str,
    since: int | None = None,
    max_bars: int | None = None,
) -> list[OHLCBar]:
    """Synchronous download using yfinance."""
    import yfinance as yf

    ticker = _convert_symbol(symbol)
    df = yf.download(ticker, period="max", interval="1d", progress=False)

    if df.empty:
        return []

    # Handle MultiIndex columns from yfinance
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.droplevel(1)

    bars: list[OHLCBar] = []
    for idx, row in df.iterrows():
        ts: int = int(idx.timestamp())
        if since and ts < since:
            continue
        bars.append(OHLCBar(
            timestamp=ts,
            open=str(row["Open"]),
            high=str(row["High"]),
            low=str(row["Low"]),
            close=str(row["Close"]),
            volume=str(row["Volume"]),
            source=ProviderName.YFINANCE.value,
        ))

    if max_bars and len(bars) > max_bars:
        bars = bars[-max_bars:]

    return bars


async def download(
    symbol: str,
    interval: Interval = Interval.D1,
    since: int | None = None,
    max_bars: int | None = None,
) -> list[OHLCBar]:
    """Download OHLC data from Yahoo Finance (daily only)."""
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(f"yfinance only supports daily interval, got {interval.value}")

    bars = await asyncio.to_thread(_download_sync, symbol, since, max_bars)
    logger.info("yfinance: fetched %d bars for %s", len(bars), symbol)
    return bars
