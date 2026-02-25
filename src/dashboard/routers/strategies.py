"""Strategy endpoints: list, detail, weight/enable control, consensus."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.dashboard.dependencies import require_user, state
from src.dashboard.schemas import UpdateEnabledRequest, UpdateWeightRequest  # noqa: TC001
from src.db.models import UserRecord  # noqa: TC001

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


def _strategy_info(s) -> dict:
    """Extract strategy info from a strategy object."""
    return {
        "name": getattr(s, "name", s.__class__.__name__),
        "type": s.__class__.__name__,
        "enabled": getattr(s, "enabled", True),
        "weight": getattr(s, "weight", 1.0),
        "description": getattr(s, "description", ""),
    }


@router.get("/")
async def list_strategies(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """All strategies with type, weight, enabled, features."""
    return [_strategy_info(s) for s in state.strategies]


@router.get("/status")
async def strategy_status(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Strategy module summary."""
    total = len(state.strategies)
    enabled = sum(1 for s in state.strategies if getattr(s, "enabled", True))
    return {
        "total": total,
        "enabled": enabled,
        "disabled": total - enabled,
        "strategies": [
            {
                "name": getattr(s, "name", s.__class__.__name__),
                "enabled": getattr(s, "enabled", True),
            }
            for s in state.strategies
        ],
    }


@router.get("/consensus")
async def get_consensus(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Current consensus state --- latest signals grouped by symbol."""
    if state.db is None:
        return {"symbols": {}}

    signals = await state.db.list_signals(limit=200)

    # Group by symbol, show each strategy's latest vote
    by_symbol: dict[str, dict[str, dict]] = {}
    for s in signals:
        if s.symbol not in by_symbol:
            by_symbol[s.symbol] = {}
        if s.strategy not in by_symbol[s.symbol]:
            by_symbol[s.symbol][s.strategy] = {
                "direction": s.direction,
                "confidence": s.confidence,
                "timestamp": s.timestamp.isoformat(),
            }

    return {"symbols": by_symbol}


@router.get("/{name}")
async def get_strategy(name: str, current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Single strategy detail + performance."""
    for s in state.strategies:
        sname = getattr(s, "name", s.__class__.__name__)
        if sname == name:
            info = _strategy_info(s)
            # Add signal history if DB available
            if state.db:
                signals = await state.db.list_signals(limit=100)
                info["recent_signals"] = [
                    {
                        "symbol": sig.symbol,
                        "direction": sig.direction,
                        "confidence": sig.confidence,
                        "timestamp": sig.timestamp.isoformat(),
                    }
                    for sig in signals
                    if sig.strategy == name
                ]
            return info
    raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")


@router.put("/{name}/weight")
async def update_weight(
    name: str,
    req: UpdateWeightRequest,
    current_user: UserRecord = Depends(require_user),  # noqa: B008
):
    """Update strategy weight."""
    for s in state.strategies:
        sname = getattr(s, "name", s.__class__.__name__)
        if sname == name:
            s.weight = req.weight
            return {"name": name, "weight": req.weight}
    raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")


@router.put("/{name}/enabled")
async def update_enabled(
    name: str,
    req: UpdateEnabledRequest,
    current_user: UserRecord = Depends(require_user),  # noqa: B008
):
    """Toggle strategy enabled/disabled."""
    for s in state.strategies:
        sname = getattr(s, "name", s.__class__.__name__)
        if sname == name:
            s.enabled = req.enabled
            return {"name": name, "enabled": req.enabled}
    raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")


@router.get("/{name}/signals")
async def get_strategy_signals(
    name: str,
    limit: int = 50,
    current_user: UserRecord = Depends(require_user),  # noqa: B008
):
    """Signal history for a specific strategy."""
    if state.db is None:
        return []
    signals = await state.db.list_signals(limit=500)
    filtered = [s for s in signals if s.strategy == name][:limit]
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "direction": s.direction,
            "confidence": s.confidence,
            "reasoning": s.reasoning,
            "timestamp": s.timestamp.isoformat(),
        }
        for s in filtered
    ]


@router.get("/{name}/performance")
async def get_strategy_performance(name: str, current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Strategy performance stats from trade history."""
    if state.db is None:
        return {"name": name, "total_trades": 0, "win_rate": 0, "total_pnl": 0}

    trades = await state.db.list_trades(strategy=name, limit=1000)
    if not trades:
        return {"name": name, "total_trades": 0, "win_rate": 0, "total_pnl": 0}

    total = len(trades)
    # Simple P&L from trade prices (buys are negative, sells positive)
    buys = [t for t in trades if t.side == "buy"]
    sells = [t for t in trades if t.side == "sell"]

    return {
        "name": name,
        "total_trades": total,
        "buys": len(buys),
        "sells": len(sells),
    }
