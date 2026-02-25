"""Signal endpoints: recent signals, filtered listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.dashboard.dependencies import require_user, state
from src.db.models import UserRecord

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/")
async def list_signals(
    limit: int = 100,
    strategy: str | None = None,
    symbol: str | None = None,
    current_user: UserRecord = Depends(require_user),
):
    """Recent signals with optional filters."""
    if state.db is None:
        return []
    signals = await state.db.list_signals(limit=limit, user_id=current_user.id)
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
async def latest_signals(current_user: UserRecord = Depends(require_user)):
    """Latest signal per strategy per symbol."""
    if state.db is None:
        return []
    signals = await state.db.list_signals(limit=500, user_id=current_user.id)
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
