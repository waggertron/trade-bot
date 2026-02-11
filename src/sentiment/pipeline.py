"""SentimentPipeline — orchestrates fetch, score, aggregate, and persist.

The pipeline ties together news providers, an article buffer, a sentiment
analyzer, an aggregator, and a persistence store into a single coherent
workflow that can be called each cycle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.sentiment.aggregator import SentimentAggregator
from src.sentiment.article_buffer import ArticleBuffer
from src.sentiment.models import Article
from src.sentiment.store import SentimentStore


class SentimentPipeline:
    """Orchestrates the full sentiment flow.

    1. **fetch** — pull articles from every news provider for the requested
       symbols, convert raw dicts to :class:`Article`, and ingest into the
       dedup buffer.
    2. **score** — drain buffered articles, run each through the sentiment
       analyzer, persist articles + scores to the store, and feed scores
       into the rolling aggregator.
    3. **get_sentiment** — return the current time-weighted aggregate for
       a single symbol.
    4. **run_cycle** — convenience wrapper: fetch + score + return sentiment
       dict for all requested symbols.
    """

    def __init__(
        self,
        news_providers: list[Any],
        analyzer: Any,
        buffer: ArticleBuffer | None = None,
        aggregator: SentimentAggregator | None = None,
        store: SentimentStore | None = None,
    ) -> None:
        self._news_providers = news_providers
        self._analyzer = analyzer
        self.buffer = buffer or ArticleBuffer()
        self.aggregator = aggregator or SentimentAggregator()
        self.store = store or SentimentStore()

    # -- public API -----------------------------------------------------------

    async def fetch(self, symbols: list[str]) -> int:
        """Fetch articles from all providers for all symbols.

        Raw dicts are converted to :class:`Article` via :meth:`_to_article`.
        Returns the total number of *new* (non-duplicate) articles ingested
        into the buffer.
        """
        all_articles: list[Article] = []

        for provider in self._news_providers:
            for symbol in symbols:
                raw_items = await provider.fetch_articles(symbol)
                for raw in raw_items:
                    article = self._to_article(raw, provider.name)
                    all_articles.append(article)

        new_count = self.buffer.ingest(all_articles)
        return new_count

    async def score(self, symbols: list[str] | None = None) -> int:
        """Drain buffer, score with analyzer, save to store, add to aggregator.

        If *symbols* is ``None``, processes all symbols currently in the buffer.
        Returns the total number of articles scored.
        """
        if symbols is None:
            symbols = self.buffer.symbols()

        total_scored = 0

        for symbol in symbols:
            articles = self.buffer.drain(symbol)
            if not articles:
                continue

            # Persist articles to store
            self.store.save_articles(articles)

            # Score each article
            scores = []
            for article in articles:
                text = f"{article.title}. {article.body}"
                result = await self._analyzer.score(text)
                # Attach article_id to the result for store lookups.
                # SentimentResult is frozen, so reconstruct with article_id.
                from src.sentiment.models import SentimentResult

                linked = SentimentResult(
                    score=result.score,
                    magnitude=result.magnitude,
                    timestamp=result.timestamp,
                    reasoning=result.reasoning,
                    article_id=article.id,
                    analyzer=result.analyzer,
                )
                scores.append(linked)

            # Persist scores and add to aggregator
            self.store.save_scores(scores)
            self.aggregator.add_scores(symbol, scores)
            total_scored += len(scores)

        return total_scored

    def get_sentiment(self, symbol: str) -> float:
        """Return the current aggregated sentiment score for *symbol*."""
        now = datetime.now(timezone.utc)
        return self.aggregator.aggregate(symbol, now)

    async def run_cycle(self, symbols: list[str]) -> dict[str, float]:
        """Fetch + score + return sentiment dict for all symbols."""
        await self.fetch(symbols)
        await self.score(symbols)
        return {symbol: self.get_sentiment(symbol) for symbol in symbols}

    # -- internals ------------------------------------------------------------

    @staticmethod
    def _to_article(raw: dict | Article, provider_name: str) -> Article:
        """Convert a raw dict (or pass-through an Article) to :class:`Article`."""
        if isinstance(raw, Article):
            return raw

        return Article(
            title=raw.get("title", ""),
            body=raw.get("body", ""),
            source=raw.get("source", provider_name),
            url=raw.get("url", ""),
            published_at=raw.get("published_at", datetime.now(timezone.utc)),
            related_symbols=raw.get("related_symbols", []),
        )
