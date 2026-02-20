"""SentimentPipeline — orchestrates fetch, score, aggregate, and persist.

Supports two modes:
1. **Legacy (in-memory):** Pass ``news_providers`` list — uses ArticleBuffer + SentimentStore.
2. **DB-backed:** Pass ``feed_manager`` + ``db`` — uses Database for dedup and persistence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.db.models import ArticleRecord
from src.processing.processors.sentiment import SentimentScoringProcessor
from src.processing.worker_pool import AsyncWorkerPool
from src.sentiment.aggregator import SentimentAggregator
from src.sentiment.article_buffer import ArticleBuffer
from src.sentiment.models import Article, SentimentResult
from src.sentiment.store import SentimentStore

if TYPE_CHECKING:
    from src.db.database import Database
    from src.feeds.manager import FeedManager

logger = logging.getLogger(__name__)


class SentimentPipeline:
    """Orchestrates the full sentiment flow."""

    def __init__(
        self,
        news_providers: list[Any] | None = None,
        analyzer: Any = None,
        buffer: ArticleBuffer | None = None,
        aggregator: SentimentAggregator | None = None,
        store: SentimentStore | None = None,
        # DB-backed mode
        feed_manager: FeedManager | None = None,
        db: Database | None = None,
    ) -> None:
        self._analyzer = analyzer
        self.aggregator = aggregator or SentimentAggregator()

        # DB-backed mode
        self._feed_manager = feed_manager
        self._db = db
        self._use_db = feed_manager is not None and db is not None

        # Legacy in-memory mode
        self._news_providers = news_providers or []
        self.buffer = buffer or ArticleBuffer()
        self.store = store or SentimentStore()

    # -- public API -----------------------------------------------------------

    async def fetch(self, symbols: list[str]) -> int:
        """Fetch articles from providers and save to DB (or buffer).

        Returns the number of *new* articles.
        """
        if self._use_db:
            return await self._fetch_db(symbols)
        return await self._fetch_legacy(symbols)

    async def score(self, symbols: list[str] | None = None) -> int:
        """Score unscored articles. Returns number scored."""
        if self._use_db:
            return await self._score_db(symbols or [])
        return await self._score_legacy(symbols)

    def get_sentiment(self, symbol: str) -> float:
        """Return the current aggregated sentiment score for *symbol*."""
        now = datetime.now(timezone.utc)
        return self.aggregator.aggregate(symbol, now)

    async def run_cycle(self, symbols: list[str]) -> dict[str, float]:
        """Fetch + score + return sentiment dict for all symbols."""
        await self.fetch(symbols)
        await self.score(symbols)
        return {symbol: self.get_sentiment(symbol) for symbol in symbols}

    async def warm_up(self, symbols: list[str], hours: int = 48) -> None:
        """Load recent scores from DB into the aggregator on startup."""
        if not self._db:
            return
        scores = await self._db.load_recent_scores(hours=hours)
        if not scores:
            return

        # Get article -> symbols mapping for each score
        for rec in scores:
            articles = await self._db.get_articles_for_symbol_by_id(rec.article_id)
            if not articles:
                continue
            article = articles[0]
            ts = rec.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            result = SentimentResult(
                score=rec.score,
                magnitude=rec.magnitude,
                timestamp=ts,
                reasoning=rec.reasoning,
                article_id=rec.article_id,
                analyzer=rec.analyzer,
            )
            for symbol in article.symbols:
                if symbol in symbols:
                    self.aggregator.add_scores(symbol, [result])

    # -- DB-backed implementations --------------------------------------------

    async def _fetch_db(self, symbols: list[str]) -> int:
        """Fetch via FeedManager, save to DB, dedup by content_hash."""
        articles = await self._feed_manager.fetch_all(symbols)
        new_count = 0
        for article in articles:
            record = ArticleRecord(
                content_hash=article.content_hash,
                title=article.title,
                body=article.body,
                source=article.source,
                url=article.url,
                published_at=article.published_at,
                fetched_at=article.fetched_at,
                symbols=article.related_symbols,
            )
            result = await self._db.save_article(record)
            if result is not None:
                new_count += 1
        return new_count

    async def _score_db(self, symbols: list[str]) -> int:
        """Score articles that haven't been scored by the current analyzer.

        Uses AsyncWorkerPool for concurrent processing (workers=1 by default,
        increase to scale when running multiple Ollama instances or switching
        to an API-backed analyzer).
        """
        analyzer_name = getattr(self._analyzer, "name", "unknown")

        # Collect unique unscored articles across all symbols
        seen_ids: set[str] = set()
        to_score: list[ArticleRecord] = []
        for symbol in symbols:
            unscored = await self._db.get_unscored_articles(symbol, analyzer_name)
            for article_rec in unscored:
                if article_rec.id not in seen_ids:
                    seen_ids.add(article_rec.id)
                    to_score.append(article_rec)

        if not to_score:
            return 0

        processor = SentimentScoringProcessor(
            analyzer=self._analyzer,
            db=self._db,
            aggregator=self.aggregator,
        )
        async with AsyncWorkerPool(processor, workers=1) as pool:
            for article_rec in to_score:
                await pool.submit(article_rec)

        return pool.processed_count

    # -- Legacy in-memory implementations -------------------------------------

    async def _fetch_legacy(self, symbols: list[str]) -> int:
        """Fetch via news_providers list into ArticleBuffer."""
        all_articles: list[Article] = []
        for provider in self._news_providers:
            for symbol in symbols:
                raw_items = await provider.fetch_articles(symbol)
                for raw in raw_items:
                    article = self._to_article(raw, provider.name)
                    all_articles.append(article)
        return self.buffer.ingest(all_articles)

    async def _score_legacy(self, symbols: list[str] | None = None) -> int:
        """Drain buffer, score, persist to SentimentStore."""
        if symbols is None:
            symbols = self.buffer.symbols()

        total_scored = 0
        for symbol in symbols:
            articles = self.buffer.drain(symbol)
            if not articles:
                continue
            self.store.save_articles(articles)
            scores = []
            for article in articles:
                text = f"{article.title}. {article.body}"
                result = await self._analyzer.score(text)
                linked = SentimentResult(
                    score=result.score,
                    magnitude=result.magnitude,
                    timestamp=result.timestamp,
                    reasoning=result.reasoning,
                    article_id=article.id,
                    analyzer=result.analyzer,
                )
                scores.append(linked)
            self.store.save_scores(scores)
            self.aggregator.add_scores(symbol, scores)
            total_scored += len(scores)
        return total_scored

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
