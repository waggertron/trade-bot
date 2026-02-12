"""News and sentiment endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from src.dashboard.dependencies import state

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/news/status")
async def news_status():
    """News providers + health."""
    return {"providers": [], "healthy": True}


@router.get("/news/feeds")
async def news_feeds():
    """Configured RSS feeds."""
    return {"feeds": []}


@router.get("/news/articles")
async def news_articles(
    symbol: str | None = None,
    source: str | None = None,
    limit: int = 50,
):
    """Articles with optional filters."""
    return []


@router.get("/sentiment/aggregate")
async def sentiment_aggregate():
    """Sentiment by symbol."""
    return {}


@router.get("/sentiment/trend")
async def sentiment_trend(symbol: str = "BTC/USD", period: str = "7d"):
    """Sentiment trend over time."""
    return {"symbol": symbol, "period": period, "points": []}
