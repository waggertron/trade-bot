"""In-memory persistence for articles and sentiment scores.

SentimentStore mirrors the eventual DB schema and provides
deduplication, filtering, and counting for articles and scores.
This will be wired to SQLAlchemy later.
"""

from __future__ import annotations

from src.sentiment.models import Article, SentimentResult


class SentimentStore:
    """In-memory store for articles and sentiment scores."""

    def __init__(self) -> None:
        self._articles: dict[str, Article] = {}  # keyed by article.id
        self._article_hashes: set[str] = set()  # for dedup
        self._scores: list[SentimentResult] = []
        self._article_symbols: dict[str, list[str]] = {}  # article_id -> symbols

    # -- Articles -------------------------------------------------------------

    def save_articles(self, articles: list[Article]) -> int:
        """Save articles, dedup by content_hash.  Return count of new articles saved."""
        saved = 0
        for article in articles:
            if article.content_hash in self._article_hashes:
                continue
            self._articles[article.id] = article
            self._article_hashes.add(article.content_hash)
            self._article_symbols[article.id] = list(article.related_symbols)
            saved += 1
        return saved

    def get_articles(
        self,
        symbol: str | None = None,
        source: str | None = None,
        limit: int = 100,
    ) -> list[Article]:
        """Return articles filtered by symbol and/or source, up to *limit*."""
        results: list[Article] = []
        for article in self._articles.values():
            if symbol is not None and symbol not in article.related_symbols:
                continue
            if source is not None and article.source != source:
                continue
            results.append(article)
            if len(results) >= limit:
                break
        return results

    def article_count(self, symbol: str | None = None) -> int:
        """Return total article count, optionally filtered by symbol."""
        if symbol is None:
            return len(self._articles)
        return sum(
            1
            for a in self._articles.values()
            if symbol in a.related_symbols
        )

    # -- Scores ---------------------------------------------------------------

    def save_scores(self, scores: list[SentimentResult]) -> int:
        """Save sentiment scores.  Return count saved."""
        self._scores.extend(scores)
        return len(scores)

    def get_scores(
        self,
        symbol: str | None = None,
        analyzer: str | None = None,
        limit: int = 100,
    ) -> list[SentimentResult]:
        """Return scores filtered by symbol (via article_id mapping) and/or analyzer."""
        results: list[SentimentResult] = []
        for s in self._scores:
            if analyzer is not None and s.analyzer != analyzer:
                continue
            if symbol is not None:
                if s.article_id is None:
                    continue
                article_symbols = self._article_symbols.get(s.article_id, [])
                if symbol not in article_symbols:
                    continue
            results.append(s)
            if len(results) >= limit:
                break
        return results

    def score_count(self, symbol: str | None = None) -> int:
        """Return total score count, optionally filtered by symbol."""
        if symbol is None:
            return len(self._scores)
        count = 0
        for s in self._scores:
            if s.article_id is None:
                continue
            article_symbols = self._article_symbols.get(s.article_id, [])
            if symbol in article_symbols:
                count += 1
        return count
