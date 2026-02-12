"""Signal endpoints: recent signals, filtered listing."""

from __future__ import annotations

from fastapi import APIRouter

from src.dashboard.dependencies import state

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/")
async def list_signals(
    limit: int = 100,
    strategy: str | None = None,
    symbol: str | None = None,
):
    """Recent signals with optional filters."""
    if state.db is None:
        return []
    signals = await state.db.list_signals(limit=limit)
    # Apply filters in memory
    if strategy:
        signals = [s for s in signals if s.strategy == strategy]
    if symbol:
        signals = [s for s in signals if s.symbol == symbol]
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "direction": s.direction,
            "confidence": s.confidence,
            "strategy": s.strategy,
            "reasoning": s.reasoning,
            "timestamp": s.timestamp.isoformat(),
        }
        for s in signals
    ]


@router.get("/latest")
async def latest_signals():
    """Latest signal per strategy per symbol."""
    if state.db is None:
        return []
    signals = await state.db.list_signals(limit=500)
    # Group by (strategy, symbol), keep first (most recent)
    seen: set[tuple[str, str]] = set()
    latest = []
    for s in signals:
        key = (s.strategy, s.symbol)
        if key not in seen:
            seen.add(key)
            latest.append({
                "id": s.id,
                "symbol": s.symbol,
                "direction": s.direction,
                "confidence": s.confidence,
                "strategy": s.strategy,
                "reasoning": s.reasoning,
                "timestamp": s.timestamp.isoformat(),
            })
    return latest
