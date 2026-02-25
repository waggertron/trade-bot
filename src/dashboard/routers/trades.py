"""Trade history endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.dashboard.dependencies import require_user, state
from src.db.models import UserRecord

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("/")
async def list_trades(
    strategy: str | None = None,
    symbol: str | None = None,
    limit: int = 100,
    offset: int = 0,
    current_user: UserRecord = Depends(require_user),
):
    """Trade history with filters."""
    if state.db is None:
        return []
    trades = await state.db.list_trades(strategy=strategy, limit=limit + offset, user_id=current_user.id)
    # Apply symbol filter and offset in memory (DB doesn't support these directly)
    if symbol:
        trades = [t for t in trades if t.symbol == symbol]
    trades = trades[offset : offset + limit]
    return [
        {
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "quantity": t.quantity,
            "price": t.price,
            "commission": t.commission,
            "strategy": t.strategy,
            "paper": t.paper,
            "timestamp": t.timestamp.isoformat(),
        }
        for t in trades
    ]


@router.get("/{trade_id}")
async def get_trade(trade_id: str, current_user: UserRecord = Depends(require_user)):
    """Single trade detail."""
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    trade = await state.db.get_trade(trade_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side,
        "quantity": trade.quantity,
        "price": trade.price,
        "commission": trade.commission,
        "strategy": trade.strategy,
        "paper": trade.paper,
        "timestamp": trade.timestamp.isoformat(),
    }
