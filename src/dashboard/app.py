# src/dashboard/app.py
from __future__ import annotations

from fastapi import FastAPI


def create_app(portfolio=None, db=None, orchestrator=None) -> FastAPI:
    app = FastAPI(title="Trade Bot Dashboard")

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/portfolio")
    async def get_portfolio():
        if portfolio is None:
            return {"error": "Portfolio not available"}
        snapshot = await portfolio.get_snapshot()
        return {
            "cash": str(snapshot.cash),
            "total_value": str(snapshot.total_value),
            "positions": [
                {
                    "symbol": p.symbol,
                    "quantity": str(p.quantity),
                    "avg_entry_price": str(p.avg_entry_price),
                    "current_price": str(p.current_price),
                    "unrealized_pnl": str(p.unrealized_pnl),
                }
                for p in snapshot.positions
            ],
        }

    @app.get("/api/trades")
    async def get_trades(strategy: str | None = None, limit: int = 100):
        if db is None:
            return []
        trades = await db.list_trades(strategy=strategy, limit=limit)
        return [
            {
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "strategy": t.strategy,
                "paper": t.paper,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in trades
        ]

    @app.get("/api/signals")
    async def get_signals(limit: int = 100):
        if db is None:
            return []
        signals = await db.list_signals(limit=limit)
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

    @app.post("/api/kill")
    async def kill_switch():
        if orchestrator:
            orchestrator.pause()
            await orchestrator._executor.cancel_all()
        return {"status": "killed", "message": "Trading halted, all orders cancelled"}

    @app.post("/api/pause")
    async def pause():
        if orchestrator:
            orchestrator.pause()
        return {"status": "paused"}

    @app.post("/api/resume")
    async def resume():
        if orchestrator:
            orchestrator.resume()
        return {"status": "resumed"}

    return app
