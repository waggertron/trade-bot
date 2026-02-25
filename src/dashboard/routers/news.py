"""News and sentiment endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.dashboard.dependencies import require_user, state
from src.db.models import UserRecord  # noqa: TC001

router = APIRouter(prefix="/api", tags=["news"])


@router.get("/news/status")
async def news_status(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """News providers + health."""
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    feed_count = await state.db.count_feeds()
    return {"feed_count": feed_count, "healthy": True}


@router.get("/news/feeds")
async def news_feeds(current_user: UserRecord = Depends(require_user)):  # noqa: B008
    """Configured RSS feeds."""
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    feeds = await state.db.list_feeds()
    return {
        "feeds": [
            {
                "id": f.id,
                "name": f.name,
                "url": f.url,
                "feed_type": f.feed_type,
                "category": f.category,
                "enabled": f.enabled,
                "last_fetched_at": f.last_fetched_at.isoformat() if f.last_fetched_at else None,
            }
            for f in feeds
        ]
    }


@router.get("/news/articles")
async def news_articles(
    symbol: str | None = None,
    source: str | None = None,
    limit: int = 50,
    current_user: UserRecord = Depends(require_user),  # noqa: B008
):
    """Articles with optional filters."""
    if state.db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    if symbol:
        articles = await state.db.get_articles_for_symbol(symbol, limit=limit)
    else:
        articles = await state.db.list_articles(source=source, limit=limit)

    return [
        {
            "id": a.id,
            "title": a.title,
            "source": a.source,
            "url": a.url,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "symbols": a.symbols,
        }
        for a in articles
    ]


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
