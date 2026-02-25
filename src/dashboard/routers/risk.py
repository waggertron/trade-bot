"""Risk management endpoints: settings, presets, regime, circuit breaker."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.core.config import RISK_LEVEL_PRESETS, RiskSettings
from src.dashboard.dependencies import require_user, state
from src.dashboard.schemas import RiskPresetRequest, RiskSettingsUpdate  # noqa: TC001
from src.db.models import UserRecord  # noqa: TC001
from src.risk.models import VolatilityRegime

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/status")
async def get_risk_status(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Current risk settings."""
    if state.risk_manager is None:
        return {"error": "Risk manager not available"}
    settings = state.risk_manager._settings
    return {
        "max_position_pct": settings.max_position_pct,
        "max_sector_exposure_pct": settings.max_sector_exposure_pct,
        "daily_loss_limit_pct": settings.daily_loss_limit_pct,
        "weekly_drawdown_limit_pct": settings.weekly_drawdown_limit_pct,
        "max_open_positions": settings.max_open_positions,
        "stop_loss_pct": settings.stop_loss_pct,
        "trailing_stop_enabled": settings.trailing_stop_enabled,
        "trailing_stop_pct": settings.trailing_stop_pct,
        "max_correlation": settings.max_correlation,
    }


@router.get("/limits")
async def get_regime_limits(
    regime: str = "medium",
    current_user: UserRecord = Depends(require_user),  # noqa: B008
):
    """Regime-specific limits."""
    from src.agents.risk_manager import REGIME_LIMITS

    try:
        vol_regime = VolatilityRegime(regime.upper() if regime[0].islower() else regime)
    except ValueError:
        # Try case-insensitive matching
        regime_map = {r.value.lower(): r for r in VolatilityRegime}
        vol_regime = regime_map.get(regime.lower())
        if vol_regime is None:
            raise HTTPException(status_code=400, detail=f"Invalid regime: {regime}") from None

    limits = REGIME_LIMITS.get(vol_regime, {})
    return {"regime": vol_regime.value, "limits": limits}


@router.get("/limits/all")
async def get_all_regime_limits(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """All regime limits."""
    from src.agents.risk_manager import REGIME_LIMITS

    return {regime.value: limits for regime, limits in REGIME_LIMITS.items()}


@router.put("/settings")
async def update_risk_settings(
    req: RiskSettingsUpdate,
    current_user: UserRecord = Depends(require_user),  # noqa: B008
):
    """Update risk parameters (partial update)."""
    if state.risk_manager is None:
        raise HTTPException(status_code=503, detail="Risk manager not available")

    current = state.risk_manager._settings
    updates = req.model_dump(exclude_none=True)
    if not updates:
        return {"message": "No changes"}

    new_settings = RiskSettings.model_validate({**current.model_dump(), **updates})
    state.risk_manager._settings = new_settings
    return {"message": "Settings updated", "settings": new_settings.model_dump()}


@router.put("/preset")
async def apply_preset(req: RiskPresetRequest, current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Apply a risk preset level."""
    if state.risk_manager is None:
        raise HTTPException(status_code=503, detail="Risk manager not available")

    new_settings = RiskSettings.from_risk_level(req.level)
    state.risk_manager._settings = new_settings
    return {"message": f"Applied {req.level} preset", "settings": new_settings.model_dump()}


@router.get("/presets")
async def get_presets(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Available risk presets."""
    return {level.value: params for level, params in RISK_LEVEL_PRESETS.items()}


@router.get("/regime")
async def get_current_regime(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Current volatility regime."""
    return {"regime": "medium", "description": "Normal market conditions"}


@router.get("/drawdown")
async def get_drawdown_status(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Daily/weekly drawdown progress."""
    if state.risk_manager is None or state.portfolio is None:
        return {"daily_pct": 0, "weekly_pct": 0, "positions_used": 0}

    settings = state.risk_manager._settings
    snapshot = await state.portfolio.get_snapshot()
    total_value = float(snapshot.total_value)

    daily_pnl = float(state.risk_manager._daily_pnl)
    daily_pct = abs(daily_pnl) / total_value * 100 if total_value > 0 and daily_pnl < 0 else 0

    return {
        "daily_pct": round(daily_pct, 2),
        "daily_limit": settings.daily_loss_limit_pct,
        "weekly_pct": 0,  # Would need weekly tracking
        "weekly_limit": settings.weekly_drawdown_limit_pct,
        "positions_used": len(snapshot.positions),
        "positions_limit": settings.max_open_positions,
    }


@router.get("/circuit-breaker")
async def get_circuit_breaker(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Circuit breaker status."""
    if state.risk_manager is None:
        return {"tripped": False, "cooldown_remaining": 0}

    cb = state.risk_manager._circuit_breaker
    if cb is None:
        return {"tripped": False, "enabled": False}

    return {
        "enabled": True,
        "tripped": getattr(cb, "_tripped", False),
        "threshold": getattr(cb, "_threshold", 0),
    }


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Manual circuit breaker reset."""
    if state.risk_manager is None:
        raise HTTPException(status_code=503, detail="Risk manager not available")

    cb = state.risk_manager._circuit_breaker
    if cb is not None and hasattr(cb, "reset"):
        cb.reset()
    return {"message": "Circuit breaker reset"}


@router.get("/decisions")
async def get_risk_decisions(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Risk decision log. Uses event bus history if available."""
    if state.event_bus is None:
        return []

    events = state.event_bus.get_history("risk_decision")
    return [
        {
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in events[-50:]
    ]
