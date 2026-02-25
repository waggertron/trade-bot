"""SentimentScoringProcessor — Processor[ArticleRecord] implementation.

Scores one article at a time, persists the result to the database, and
optionally feeds the in-memory SentimentAggregator.

Already-scored articles are skipped (idempotent).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from src.db.models import ArticleRecord, SentimentScoreRecord
from src.sentiment.models import SentimentResult

if TYPE_CHECKING:
    from src.db.database import Database
    from src.sentiment.aggregator import SentimentAggregator


class SentimentScoringProcessor:
    """Processes an ArticleRecord: score → persist → aggregate."""

    def __init__(
        self,
        analyzer: Any,
        db: Database,
        aggregator: SentimentAggregator | None = None,
    ) -> None:
        self._analyzer = analyzer
        self._db = db
        self._aggregator = aggregator

    @property
    def name(self) -> str:
        return "sentiment_scoring"

    async def process(self, article: ArticleRecord) -> None:
        """Score *article* and persist the result.

        No-ops if the article already has a score for the current analyzer.
        """
        if await self._db.has_score(article.id, self._analyzer.name):
            return

        text = f"{article.title}. {article.body}"
        result = await self._analyzer.score(text)

        score_rec = SentimentScoreRecord(
            article_id=article.id,
            score=result.score,
            magnitude=result.magnitude,
            reasoning=result.reasoning,
            analyzer=self._analyzer.name,
        )
        await self._db.save_score(score_rec)

        if self._aggregator is not None:
            sentiment_result = SentimentResult(
                score=result.score,
                magnitude=result.magnitude,
                timestamp=datetime.now(UTC),
                reasoning=result.reasoning,
                article_id=article.id,
                analyzer=self._analyzer.name,
            )
            for symbol in article.symbols:
                self._aggregator.add_scores(symbol, [sentiment_result])
