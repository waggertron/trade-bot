"""FastAPI application factory with router-based architecture."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.dashboard import dependencies
from src.dashboard.rate_limit import RateLimitMiddleware
from src.dashboard.request_id import RequestIDMiddleware
from src.dashboard.routers import (
    analytics,
    auth,
    backtest,
    config,
    market,
    ml,
    news,
    oauth,
    portfolio,
    risk,
    signals,
    simulation,
    strategies,
    trades,
    trading,
    websocket,
)
from src.dashboard.security_headers import SecurityHeadersMiddleware


def create_app(
    portfolio_manager=None,
    db=None,
    orchestrator=None,
    executor=None,
    risk_manager=None,
    event_bus=None,
    settings=None,
    strategy_list=None,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Trade Bot Dashboard", version="2.0.0")

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Request ID tracking
    app.add_middleware(RequestIDMiddleware)

    # Rate limiting (100 reads/min, 10 writes/min per user)
    app.add_middleware(RateLimitMiddleware, read_limit=100, write_limit=10)

    # CORS — configurable via ALLOWED_ORIGINS env var
    allowed_origins = os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in allowed_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Populate shared state
    dependencies.state.portfolio = portfolio_manager
    dependencies.state.db = db
    dependencies.state.orchestrator = orchestrator
    dependencies.state.executor = executor
    dependencies.state.risk_manager = risk_manager
    dependencies.state.event_bus = event_bus
    dependencies.state.settings = settings
    dependencies.state.strategies = strategy_list or []
    dependencies.state.start_time = datetime.now(UTC)

    # Register routers
    app.include_router(auth.router)
    app.include_router(oauth.router)
    app.include_router(portfolio.router)
    app.include_router(trading.router)
    app.include_router(trades.router)
    app.include_router(signals.router)
    app.include_router(strategies.router)
    app.include_router(analytics.router)
    app.include_router(risk.router)
    app.include_router(backtest.router)
    app.include_router(news.router)
    app.include_router(ml.router)
    app.include_router(config.router)
    app.include_router(market.router)
    app.include_router(simulation.router)
    app.include_router(websocket.router)

    # System endpoints (kept inline)
    @app.get("/api/health")
    async def health():
        db_status = "not configured"
        status = "ok"
        if dependencies.state.db is not None:
            try:
                await dependencies.state.db.check_health()
                db_status = "connected"
            except Exception:
                db_status = "disconnected"
                status = "degraded"
        return {"status": status, "database": db_status}

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

    @app.get("/api/system/status")
    async def system_status():
        is_paused = orchestrator.is_paused if orchestrator else False
        mode = settings.mode if settings else "paper"
        uptime = (datetime.now(UTC) - dependencies.state.start_time).total_seconds()
        return {
            "mode": mode,
            "is_paused": is_paused,
            "uptime_seconds": int(uptime),
            "strategies_count": len(dependencies.state.strategies),
        }

    return app
