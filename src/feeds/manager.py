"""FeedManager — loads feeds from DB, creates adapters, orchestrates fetching."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from src.db.models import FeedRecord
from src.sentiment.models import Article

logger = logging.getLogger(__name__)


class FeedManager:
    """Loads enabled feeds from the database, groups by type, and orchestrates fetching."""

    def __init__(self, db: "Database") -> None:  # noqa: F821
        self._db = db
        self.feeds: list[FeedRecord] = []
        self.feeds_by_type: dict[str, list[FeedRecord]] = {}

    async def load_feeds(self) -> None:
        """Load enabled feeds from DB and group by feed_type."""
        self.feeds = await self._db.list_feeds(enabled_only=True)
        grouped: dict[str, list[FeedRecord]] = defaultdict(list)
        for f in self.feeds:
            grouped[f.feed_type].append(f)
        self.feeds_by_type = dict(grouped)

    async def has_feeds(self) -> bool:
        """Check whether any feeds exist in the database."""
        return await self._db.count_feeds() > 0

    async def fetch_all(self, symbols: list[str]) -> list[Article]:
        """Fan out across all adapters, collect articles."""
        from src.providers.government import GovernmentFeedAdapter
        from src.providers.json_api import JSONAPIAdapter
        from src.providers.rss import RSSNewsProvider

        all_articles: list[Article] = []

        adapter_map = {
            "rss": lambda feeds: RSSNewsProvider.from_feed_records(feeds),
            "json_api": lambda feeds: JSONAPIAdapter(feeds),
            "government": lambda feeds: GovernmentFeedAdapter(feeds),
        }

        for feed_type, feeds in self.feeds_by_type.items():
            factory = adapter_map.get(feed_type)
            if factory is None:
                logger.warning("Unknown feed_type: %s", feed_type)
                continue
            adapter = factory(feeds)
            for symbol in symbols:
                try:
                    articles = await adapter.fetch_articles(symbol)
                    all_articles.extend(articles)
                except Exception:
                    logger.warning(
                        "Error fetching %s from %s adapter",
                        symbol, feed_type, exc_info=True,
                    )

        return all_articles

    async def update_last_fetched(self, feed_id: str) -> None:
        """Update last_fetched_at after successful fetch."""
        await self._db.update_feed_last_fetched(feed_id, datetime.now(timezone.utc))
