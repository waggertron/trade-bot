"""Government feed adapter — fetches from government data sources."""

from __future__ import annotations

import asyncio
import calendar
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import feedparser

from src.sentiment.models import Article

if TYPE_CHECKING:
    from time import struct_time

    from src.db.models import FeedRecord

logger = logging.getLogger(__name__)

# Government feeds that are actually RSS/XML
RSS_EXTENSIONS = (".xml", ".rss")
RSS_PATH_PATTERNS = ("/feeds/", "/rss/", "/feed/")


class GovernmentFeedAdapter:
    """Adapter for government data sources (Fed, SEC, Treasury, etc.).

    Many government endpoints serve RSS/XML; some serve JSON. This adapter
    detects the format and delegates accordingly.
    """

    def __init__(self, feeds: list[FeedRecord]) -> None:
        self._feeds = feeds

    @property
    def name(self) -> str:
        return "government"

    @property
    def rate_limit(self) -> int:
        if self._feeds:
            return min(f.rate_limit_rpm for f in self._feeds)
        return 60

    async def fetch_articles(self, symbol: str, limit: int = 10) -> list[Article]:
        articles: list[Article] = []
        for feed in self._feeds:
            try:
                if self._is_rss(feed.url):
                    items = await self._fetch_rss(feed, symbol)
                else:
                    items = await self._fetch_json(feed, symbol)
                articles.extend(items)
            except Exception:
                logger.warning("Failed to fetch from %s", feed.name, exc_info=True)
        return articles[:limit]

    async def health_check(self) -> bool:
        return True

    @staticmethod
    def _is_rss(url: str) -> bool:
        lower = url.lower()
        return any(lower.endswith(ext) for ext in RSS_EXTENSIONS) or any(
            pat in lower for pat in RSS_PATH_PATTERNS
        )

    async def _fetch_rss(self, feed: FeedRecord, symbol: str) -> list[Article]:
        parsed = await asyncio.to_thread(feedparser.parse, feed.url)
        articles = []
        for entry in parsed.get("entries", []):
            title = entry.get("title", "")
            if not title:
                continue
            articles.append(
                Article(
                    title=title,
                    body=entry.get("summary", ""),
                    source=feed.name,
                    url=entry.get("link", ""),
                    published_at=_parse_time(entry.get("published_parsed")),
                    related_symbols=[symbol],
                )
            )
        return articles

    async def _fetch_json(self, feed: FeedRecord, symbol: str) -> list[Article]:
        import httpx

        headers = {}
        if "sec.gov" in feed.url:
            headers["User-Agent"] = "trade-bot/1.0 (contact@example.com)"

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            resp = await client.get(feed.url)
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for key in ("data", "results", "filings", "recent"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
            else:
                items = [data]
        else:
            items = []

        articles = []
        for item in items:
            title = item.get("title") or item.get("name") or ""
            if not title:
                continue
            articles.append(
                Article(
                    title=title,
                    body=item.get("summary") or item.get("description") or "",
                    source=feed.name,
                    url=item.get("url") or item.get("link") or "",
                    published_at=datetime.now(UTC),
                    related_symbols=[symbol],
                )
            )
        return articles


def _parse_time(t: struct_time | tuple | None) -> datetime:
    if t is None:
        return datetime.now(UTC)
    ts = calendar.timegm(t)
    return datetime.fromtimestamp(ts, tz=UTC)
