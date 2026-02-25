"""News and sentiment endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.dashboard.dependencies import require_user
from src.db.models import UserRecord  # noqa: TC001

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/news/status")
async def news_status(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """News providers + health."""
    return {"providers": [], "healthy": True}


@router.get("/news/feeds")
async def news_feeds(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Configured RSS feeds."""
    return {"feeds": []}


@router.get("/news/articles")
async def news_articles(
    symbol: str | None = None,
    source: str | None = None,
    limit: int = 50,
    current_user: UserRecord = Depends(require_user),  # noqa: B008
):
    """Articles with optional filters."""
    return []


@router.get("/sentiment/aggregate")
async def sentiment_aggregate(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Sentiment by symbol."""
    return {}


@router.get("/sentiment/trend")
async def sentiment_trend(
    symbol: str = "BTC/USD",
    period: str = "7d",
    current_user: UserRecord = Depends(require_user),  # noqa: B008
):
    """Sentiment trend over time."""
    return {"symbol": symbol, "period": period, "points": []}
