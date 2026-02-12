"""Configuration endpoints: settings CRUD, mode, symbols."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.dashboard.dependencies import state
from src.dashboard.schemas import UpdateModeRequest, UpdateSymbolsRequest

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/")
async def get_config():
    """Full settings."""
    if state.settings is None:
        return {"error": "Settings not available"}
    return state.settings.model_dump()


@router.get("/mode")
async def get_mode():
    """Current mode (paper/live)."""
    if state.settings is None:
        return {"mode": "paper"}
    return {"mode": state.settings.mode}


@router.put("/mode")
async def set_mode(req: UpdateModeRequest):
    """Switch paper/live mode."""
    if state.settings is None:
        raise HTTPException(status_code=503, detail="Settings not available")
    # Settings are frozen, so we rebuild
    data = state.settings.model_dump()
    data["mode"] = req.mode
    from src.core.config import Settings
    state.settings = Settings.model_validate(data)
    return {"mode": req.mode}


@router.get("/symbols")
async def get_symbols():
    """Current watchlist."""
    if state.settings is None:
        return {"stocks": [], "crypto": []}
    return {
        "stocks": state.settings.trading.symbols.stocks,
        "crypto": state.settings.trading.symbols.crypto,
    }


@router.put("/symbols")
async def update_symbols(req: UpdateSymbolsRequest):
    """Update watchlist."""
    if state.settings is None:
        raise HTTPException(status_code=503, detail="Settings not available")
    data = state.settings.model_dump()
    data["trading"]["symbols"]["stocks"] = req.stocks
    data["trading"]["symbols"]["crypto"] = req.crypto
    from src.core.config import Settings
    state.settings = Settings.model_validate(data)
    return {"stocks": req.stocks, "crypto": req.crypto}
