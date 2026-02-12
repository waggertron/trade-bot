"""ML and feature endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from src.dashboard.dependencies import state

router = APIRouter(prefix="/api", tags=["ml"])


@router.get("/features/catalog")
async def feature_catalog():
    """Feature catalog by category."""
    return {
        "technical": [
            "sma_14", "sma_50", "ema_12", "ema_26", "rsi_14",
            "macd", "macd_signal", "bollinger_upper", "bollinger_lower",
            "atr_14", "volume_sma_20",
        ],
        "sentiment": [
            "sentiment_avg_6h", "sentiment_velocity",
            "article_volume_ratio", "sentiment_dispersion",
        ],
        "cross_asset": [
            "btc_eth_correlation", "crypto_stock_correlation",
        ],
        "on_chain": [
            "active_addresses", "transaction_volume", "exchange_flows",
        ],
    }


@router.get("/features/status")
async def feature_status():
    """Feature engine status."""
    return {"status": "idle", "last_update": None, "features_available": 0}


@router.get("/ml/models")
async def list_models():
    """Trained models with metrics."""
    return []


@router.get("/ml/models/{name}/importance")
async def model_importance(name: str):
    """Feature importance for a specific model."""
    return {"model": name, "features": []}


@router.post("/ml/train")
async def trigger_training():
    """Trigger model training."""
    return {"status": "training_started"}


@router.get("/ml/predictions")
async def get_predictions():
    """Latest predictions by symbol."""
    return {}
