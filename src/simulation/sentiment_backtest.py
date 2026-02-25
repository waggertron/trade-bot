"""SentimentBacktestLoader — pre-loads all sentiment data for lookahead-free replay."""

from __future__ import annotations

import bisect
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.sentiment.aggregator import SentimentAggregator
from src.sentiment.bridge import SentimentBridge
from src.sentiment.models import SentimentResult

if TYPE_CHECKING:
    from src.core.models import ResearchReport


class SentimentBacktestLoader:
    """Pre-loads all sentiment data from DB; provides lookahead-free ResearchReports per tick.

    Call ``await loader.load()`` once, then use ``loader.get_research_at(dt)``
    at each simulated tick to get reports containing only articles published ≤ dt.
    """

    def __init__(self, db, symbols: list[str], analyzer: str | None = None) -> None:
        self._db = db
        self._symbols = symbols
        self._analyzer = analyzer
        # Sorted list of (published_at, symbol, score, magnitude)
        self._rows: list[tuple[datetime, str, float, float]] = []
        # Sorted timestamps for bisect slicing
        self._timestamps: list[datetime] = []
        # Cache: date -> list[ResearchReport]
        self._cache: dict[object, list[ResearchReport]] = {}

    async def load(self) -> None:
        """Pull ALL scored articles from DB into memory, sorted by published_at."""
        far_future = datetime(9999, 12, 31, tzinfo=UTC)
        raw = await self._db.get_scores_as_of(self._symbols, far_future, self._analyzer)
        # raw = list of (symbol, score, magnitude, published_at)
        # Sort by published_at ascending
        self._rows = sorted(
            (
                (published_at, symbol, score, magnitude)
                for symbol, score, magnitude, published_at in raw
            ),
            key=lambda r: r[0],
        )
        self._timestamps = [r[0] for r in self._rows]

    def get_research_at(self, as_of_dt: datetime) -> list[ResearchReport]:
        """Return ResearchReports using only articles with published_at ≤ as_of_dt.

        Cached per calendar date so repeated calls within the same daily bar
        return the same list object.
        """
        cache_key = as_of_dt.date()
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Use bisect to find the right-most index where published_at <= as_of_dt
        # bisect_right gives us the insertion point after all equal values
        cutoff_idx = bisect.bisect_right(self._timestamps, as_of_dt)
        visible_rows = self._rows[:cutoff_idx]

        if not visible_rows:
            result: list[ResearchReport] = []
            self._cache[cache_key] = result
            return result

        # Build aggregator with all visible scores
        aggregator = SentimentAggregator()
        for published_at, symbol, score, magnitude in visible_rows:
            result_obj = SentimentResult(
                score=score,
                magnitude=magnitude,
                timestamp=published_at,
            )
            aggregator.add_scores(symbol, [result_obj])

        reports = SentimentBridge(aggregator).to_research_reports(self._symbols)
        self._cache[cache_key] = reports
        return reports

    @property
    def coverage(self) -> dict:
        """Return coverage statistics about the loaded data."""
        if not self._rows:
            return {
                "symbols": self._symbols,
                "min_date": None,
                "max_date": None,
                "total_articles": 0,
                "articles_per_day": {},
            }

        min_date = self._rows[0][0]
        max_date = self._rows[-1][0]

        articles_per_day: dict[object, int] = {}
        for published_at, _symbol, _score, _magnitude in self._rows:
            day = published_at.date()
            articles_per_day[day] = articles_per_day.get(day, 0) + 1

        return {
            "symbols": self._symbols,
            "min_date": min_date,
            "max_date": max_date,
            "total_articles": len(self._rows),
            "articles_per_day": articles_per_day,
        }
