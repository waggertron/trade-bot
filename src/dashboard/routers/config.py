"""Configuration endpoints: per-user settings via DB, with global fallback."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from src.dashboard.dependencies import require_user, state
from src.dashboard.schemas import UpdateModeRequest, UpdateSymbolsRequest  # noqa: TC001
from src.db.models import UserRecord, UserSettingsRecord

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/")
async def get_config(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Full settings --- per-user from DB, falling back to global."""
    if state.db is not None:
        user_settings = await state.db.get_user_settings(current_user.id)
        if user_settings is not None:
            symbols = (
                json.loads(user_settings.symbols_config)
                if user_settings.symbols_config
                else {"stocks": [], "crypto": []}
            )
            weights = (
                json.loads(user_settings.strategy_weights) if user_settings.strategy_weights else {}
            )
            return {
                "mode": user_settings.mode,
                "risk_preset": user_settings.risk_preset,
                "symbols": symbols,
                "strategy_weights": weights,
            }
    if state.settings is None:
        return {"error": "Settings not available"}
    return state.settings.model_dump()


@router.get("/mode")
async def get_mode(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Current mode (paper/live) --- per-user."""
    if state.db is not None:
        user_settings = await state.db.get_user_settings(current_user.id)
        if user_settings is not None:
            return {"mode": user_settings.mode}
    if state.settings is None:
        return {"mode": "paper"}
    return {"mode": state.settings.mode}


@router.put("/mode")
async def set_mode(req: UpdateModeRequest, current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Switch paper/live mode --- persisted to DB per-user."""
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    user_settings = await state.db.get_user_settings(current_user.id)
    if user_settings is None:
        await state.db.save_user_settings(
            UserSettingsRecord(user_id=current_user.id, mode=req.mode)
        )
    else:
        await state.db.update_user_settings(current_user.id, mode=req.mode)
    return {"mode": req.mode}


@router.get("/symbols")
async def get_symbols(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Current watchlist --- per-user."""
    if state.db is not None:
        user_settings = await state.db.get_user_settings(current_user.id)
        if user_settings is not None and user_settings.symbols_config:
            config = json.loads(user_settings.symbols_config)
            return {"stocks": config.get("stocks", []), "crypto": config.get("crypto", [])}
    if state.settings is None:
        return {"stocks": [], "crypto": []}
    return {
        "stocks": state.settings.trading.symbols.stocks,
        "crypto": state.settings.trading.symbols.crypto,
    }


@router.put("/symbols")
async def update_symbols(
    req: UpdateSymbolsRequest,
    current_user: UserRecord = Depends(require_user),  # noqa: B008
):
    """Update watchlist --- persisted to DB per-user."""
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    symbols_json = json.dumps({"stocks": req.stocks, "crypto": req.crypto})
    user_settings = await state.db.get_user_settings(current_user.id)
    if user_settings is None:
        await state.db.save_user_settings(
            UserSettingsRecord(user_id=current_user.id, symbols_config=symbols_json)
        )
    else:
        await state.db.update_user_settings(current_user.id, symbols_config=symbols_json)
    return {"stocks": req.stocks, "crypto": req.crypto}
