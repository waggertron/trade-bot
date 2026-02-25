"""Market data endpoints: OHLC bars, prices, sparklines."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.dashboard.dependencies import require_user, state
from src.db.models import UserRecord

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/ohlc/{symbol}")
async def get_ohlc(
    symbol: str,
    interval: str = "1h",
    start: int | None = None,
    end: int | None = None,
    limit: int = 500,
    current_user: UserRecord = Depends(require_user),
):
    """OHLC bars for charting."""
    if state.db is None:
        return []

    # URL-decode symbol (e.g., BTC%2FUSD -> BTC/USD)
    symbol = symbol.replace("%2F", "/")

    bars = await state.db.query_ohlc_bars(
        symbol=symbol,
        interval=interval,
        start_ts=start,
        end_ts=end,
        limit=limit,
    )
    return [
        {
            "timestamp": bar.timestamp,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in bars
    ]


@router.get("/prices")
async def get_current_prices(current_user: UserRecord = Depends(require_user)):
    """Current prices for all symbols from executor."""
    if state.executor is None:
        return {}
    return {
        symbol: str(price)
        for symbol, price in state.executor._current_prices.items()
    }


@router.get("/sparklines")
async def get_sparklines(points: int = 24, current_user: UserRecord = Depends(require_user)):
    """Mini price arrays for watchlist sparklines."""
    if state.db is None:
        return {}

    # Get recent OHLC bars for each symbol
    bars = await state.db.query_ohlc_bars(limit=5000)
    if not bars:
        return {}

    # Group by symbol, take last N close prices
    from collections import defaultdict
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for bar in bars:
        by_symbol[bar.symbol].append({
            "timestamp": bar.timestamp,
            "close": float(bar.close),
        })

    result = {}
    for symbol, data in by_symbol.items():
        data.sort(key=lambda x: x["timestamp"])
        closes = [d["close"] for d in data[-points:]]
        current = closes[-1] if closes else 0
        prev = closes[0] if closes else 0
        change_pct = ((current - prev) / prev * 100) if prev > 0 else 0
        result[symbol] = {
            "prices": closes,
            "current": current,
            "change_pct": round(change_pct, 2),
        }

    return result
