"""ArticleBuffer — deduplication and per-symbol queuing for news articles.

Multiple news providers may return the same article.  The buffer
deduplicates by ``content_hash`` and queues articles by symbol so that
downstream scoring only processes each piece of content once.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.sentiment.models import Article


class ArticleBuffer:
    """Deduplicates articles by content hash and queues them per symbol.

    Parameters
    ----------
    max_age:
        How long a content hash is remembered.  After expiry the same
        article can be re-ingested (useful for long-running processes).
    """

    def __init__(self, max_age: timedelta = timedelta(hours=24)) -> None:
        self._max_age = max_age
        self._seen: dict[str, datetime] = {}  # content_hash -> first_seen
        self._queue: defaultdict[str, list[Article]] = defaultdict(list)

    # -- public API -----------------------------------------------------------

    def ingest(self, articles: list[Article]) -> int:
        """Add articles, skip duplicates by content_hash, queue by symbol.

        Returns the count of new (non-duplicate) articles ingested.
        """
        new_count = 0
        now = datetime.now(UTC)

        for article in articles:
            if article.content_hash in self._seen:
                continue

            self._seen[article.content_hash] = now
            new_count += 1

            for symbol in article.related_symbols:
                self._queue[symbol].append(article)

        return new_count

    def drain(self, symbol: str) -> list[Article]:
        """Return and clear queued articles for *symbol*."""
        articles = self._queue.pop(symbol, [])
        return articles

    def symbols(self) -> list[str]:
        """Return symbols that have pending articles."""
        return [sym for sym, arts in self._queue.items() if arts]

    def pending_count(self, symbol: str) -> int:
        """Return count of pending articles for *symbol*."""
        return len(self._queue.get(symbol, []))

    def expire(self) -> int:
        """Remove hashes older than *max_age* so they can be re-ingested.

        Returns the count of hashes removed.
        """
        now = datetime.now(UTC)
        expired = [h for h, seen_at in self._seen.items() if (now - seen_at) >= self._max_age]
        for h in expired:
            del self._seen[h]
        return len(expired)
