"""SentimentBridge — converts aggregated pipeline scores into ResearchReports
so the existing SentimentStrategy can consume real sentiment data.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.core.models import ResearchReport
from src.sentiment.aggregator import SentimentAggregator


class SentimentBridge:
    """Bridge between the sentiment pipeline and the strategy layer.

    Reads aggregated scores from a :class:`SentimentAggregator` and
    converts them into :class:`ResearchReport` instances that the
    ``SentimentStrategy`` already knows how to consume.
    """

    def __init__(self, aggregator: SentimentAggregator) -> None:
        self._aggregator = aggregator

    def to_research_reports(self, symbols: list[str]) -> list[ResearchReport]:
        """Build a :class:`ResearchReport` for each *symbol* that has scores.

        Symbols not present in the aggregator are silently skipped.
        The ``sentiment_score`` is clamped to ``[-1.0, 1.0]``.
        """
        now = datetime.now(timezone.utc)
        reports: list[ResearchReport] = []

        for symbol in symbols:
            # Skip if no scores exist for this symbol
            if symbol not in self._aggregator.symbols():
                continue

            score = self._aggregator.aggregate(symbol, now)

            reports.append(
                ResearchReport(
                    symbol=symbol,
                    summary=f"Aggregated sentiment score: {score:.3f}",
                    sentiment_score=max(-1.0, min(1.0, score)),
                    timestamp=now,
                    sources=["sentiment_pipeline"],
                )
            )

        return reports
