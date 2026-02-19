"""JSON API feed adapter — fetches articles from REST API endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from src.db.models import FeedRecord
from src.sentiment.models import Article

logger = logging.getLogger(__name__)


class JSONAPIAdapter:
    """Adapter for JSON REST API news sources (Finnhub, HN, CoinDesk, etc.)."""

    def __init__(self, feeds: list[FeedRecord]) -> None:
        self._feeds = feeds

    @property
    def name(self) -> str:
        return "json_api"

    @property
    def rate_limit(self) -> int:
        if self._feeds:
            return min(f.rate_limit_rpm for f in self._feeds)
        return 60

    async def fetch_articles(self, symbol: str, limit: int = 10) -> list[Article]:
        articles: list[Article] = []
        for feed in self._feeds:
            try:
                raw_items = await self._fetch_url(feed.url)
                for item in raw_items[:limit]:
                    article = self._to_article(item, feed, symbol)
                    if article:
                        articles.append(article)
            except Exception:
                logger.warning("Failed to fetch from %s", feed.name, exc_info=True)
        return articles[:limit]

    async def health_check(self) -> bool:
        return True

    async def _fetch_url(self, url: str) -> list[dict[str, Any]]:
        """Fetch JSON from a URL and return a list of items."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Common patterns: {"articles": [...]}, {"results": [...]}, {"data": [...]}
            for key in ("articles", "results", "data", "news", "items"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
        return []

    @staticmethod
    def _to_article(
        item: dict[str, Any], feed: FeedRecord, symbol: str,
    ) -> Article | None:
        title = item.get("title") or item.get("headline") or ""
        if not title:
            return None

        body = item.get("summary") or item.get("description") or item.get("body") or ""
        url = item.get("url") or item.get("link") or ""

        # Parse published time from various formats
        pub_raw = item.get("published_at") or item.get("publishedAt") or item.get("datetime") or item.get("time")
        if isinstance(pub_raw, (int, float)):
            published_at = datetime.fromtimestamp(pub_raw, tz=timezone.utc)
        elif isinstance(pub_raw, str):
            try:
                published_at = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
            except ValueError:
                published_at = datetime.now(timezone.utc)
        else:
            published_at = datetime.now(timezone.utc)

        return Article(
            title=title,
            body=body,
            source=feed.name,
            url=url,
            published_at=published_at,
            related_symbols=[symbol],
        )
