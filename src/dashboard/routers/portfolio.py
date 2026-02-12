"""Portfolio endpoints: snapshot, positions, P&L, equity curve, allocation."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from src.dashboard.dependencies import state

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/")
async def get_portfolio():
    """Portfolio snapshot: cash, positions, total value."""
    if state.portfolio is None:
        return {"error": "Portfolio not available"}
    snapshot = await state.portfolio.get_snapshot()
    return {
        "cash": str(snapshot.cash),
        "total_value": str(snapshot.total_value),
        "positions": [
            {
                "symbol": p.symbol,
                "quantity": str(p.quantity),
                "avg_entry_price": str(p.avg_entry_price),
                "current_price": str(p.current_price),
                "market_value": str(p.market_value),
                "unrealized_pnl": str(p.unrealized_pnl),
                "asset_type": p.asset_type.value,
            }
            for p in snapshot.positions
        ],
    }


@router.get("/positions")
async def get_positions():
    """Detailed positions with current prices."""
    if state.portfolio is None:
        return []
    positions = await state.portfolio.get_positions()
    return [
        {
            "symbol": p.symbol,
            "quantity": str(p.quantity),
            "avg_entry_price": str(p.avg_entry_price),
            "current_price": str(p.current_price),
            "market_value": str(p.market_value),
            "unrealized_pnl": str(p.unrealized_pnl),
            "asset_type": p.asset_type.value,
            "sector": p.sector,
        }
        for p in positions
    ]


@router.get("/pnl")
async def get_pnl(period: str = "30d"):
    """P&L summary: realized, unrealized, win rate."""
    if state.portfolio is None:
        return {"realized_pnl": "0", "unrealized_pnl": "0", "win_rate": 0}

    realized = await state.portfolio.get_pnl(period)
    positions = await state.portfolio.get_positions()
    unrealized = sum(float(p.unrealized_pnl) for p in positions)

    # Compute win rate from realized trades
    realized_pnls = state.portfolio._realized_pnl
    wins = sum(1 for p in realized_pnls if p > 0)
    total = len(realized_pnls)
    win_rate = wins / total if total > 0 else 0

    return {
        "realized_pnl": str(realized),
        "unrealized_pnl": str(unrealized),
        "total_pnl": str(realized + unrealized),
        "win_rate": win_rate,
        "total_trades": total,
        "winning_trades": wins,
    }


@router.get("/equity-curve")
async def get_equity_curve(range: str = "1M"):
    """Equity curve data points. Returns stored equity history or current snapshot."""
    if state.portfolio is None:
        return {"points": []}

    # Build from fill history - reconstruct equity over time
    fills = state.portfolio._fills
    initial_cash = float(state.portfolio._cash) + sum(
        float(f.fill_price * f.quantity) if f.side.value == "buy" else -float(f.fill_price * f.quantity)
        for f in fills
    )

    points = [{"timestamp": state.start_time.isoformat(), "value": initial_cash}]
    running = initial_cash
    for fill in fills:
        pnl_impact = float(fill.fill_price * fill.quantity)
        if fill.side.value == "sell":
            running += pnl_impact
        else:
            running -= pnl_impact
        points.append({
            "timestamp": fill.timestamp.isoformat(),
            "value": running,
        })

    # Add current value
    snapshot = await state.portfolio.get_snapshot()
    points.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "value": float(snapshot.total_value),
    })

    return {"points": points}


@router.get("/allocation")
async def get_allocation():
    """Asset allocation breakdown by type and sector."""
    if state.portfolio is None:
        return {"by_type": {}, "by_sector": {}, "cash_pct": 100}

    snapshot = await state.portfolio.get_snapshot()
    total = float(snapshot.total_value)
    if total <= 0:
        return {"by_type": {}, "by_sector": {}, "cash_pct": 100}

    by_type: dict[str, float] = {}
    by_sector: dict[str, float] = {}

    for p in snapshot.positions:
        mv = float(p.market_value)
        pct = mv / total * 100

        asset_type = p.asset_type.value
        by_type[asset_type] = by_type.get(asset_type, 0) + pct

        sector = p.sector or "Other"
        by_sector[sector] = by_sector.get(sector, 0) + pct

    cash_pct = float(snapshot.cash) / total * 100

    return {
        "by_type": by_type,
        "by_sector": by_sector,
        "cash_pct": cash_pct,
    }
