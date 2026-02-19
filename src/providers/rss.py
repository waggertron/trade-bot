"""RSS news provider — fetches articles from RSS feeds using feedparser."""

from __future__ import annotations

import asyncio
import calendar
from datetime import datetime, timezone
from time import struct_time
from typing import TYPE_CHECKING

import feedparser

from src.providers.configs import RSSConfig
from src.sentiment.models import Article

if TYPE_CHECKING:
    from src.db.models import FeedRecord


class RSSNewsProvider:
    """Fetches news articles from configured RSS feed URLs.

    Uses ``feedparser`` to parse RSS/Atom feeds and maps entries to
    :class:`Article` instances.  Feed parsing is offloaded to a thread
    via ``asyncio.to_thread`` so it doesn't block the event loop.
    """

    def __init__(self, config: RSSConfig) -> None:
        self._config = config

    @classmethod
    def from_feed_records(cls, feeds: list[FeedRecord]) -> RSSNewsProvider:
        """Create an RSSNewsProvider from database FeedRecord objects."""
        urls = [f.url for f in feeds]
        rate_limit = min((f.rate_limit_rpm for f in feeds), default=50)
        config = RSSConfig(feed_urls=urls, max_articles_per_fetch=rate_limit)
        return cls(config)

    @property
    def name(self) -> str:
        return "rss"

    @property
    def rate_limit(self) -> int:
        return self._config.max_articles_per_fetch

    async def fetch_articles(self, symbol: str, limit: int = 10) -> list[Article]:
        """Parse all configured feed URLs and return up to *limit* articles."""
        articles: list[Article] = []

        for url in self._config.feed_urls:
            feed = await asyncio.to_thread(feedparser.parse, url)
            for entry in feed["entries"]:
                title = entry.get("title", "")
                if not title:
                    continue
                articles.append(
                    Article(
                        title=title,
                        body=entry.get("summary", ""),
                        source="rss",
                        url=entry.get("link", ""),
                        published_at=self._parse_time(entry.get("published_parsed")),
                        related_symbols=[symbol],
                    )
                )

        return articles[:limit]

    async def health_check(self) -> bool:
        """RSS feeds are always considered available."""
        return True

    @staticmethod
    def _parse_time(t: struct_time | tuple | None) -> datetime:
        """Convert a ``struct_time`` (or compatible tuple) to a UTC datetime.

        If *t* is ``None``, returns the current UTC time.
        """
        if t is None:
            return datetime.now(timezone.utc)
        ts = calendar.timegm(t)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
