"""Tests for SentimentBridge — converting aggregated scores to ResearchReports."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.core.models import ResearchReport
from src.sentiment.aggregator import SentimentAggregator
from src.sentiment.bridge import SentimentBridge
from src.sentiment.models import SentimentResult


def _make_result(
    score: float = 0.5,
    magnitude: float = 1.0,
    timestamp: datetime | None = None,
) -> SentimentResult:
    """Helper to create a SentimentResult with sensible defaults."""
    return SentimentResult(
        score=score,
        magnitude=magnitude,
        timestamp=timestamp or datetime.now(UTC),
    )


class TestSentimentBridge:
    """Tests for SentimentBridge.to_research_reports."""

    def test_returns_report_for_symbol_with_scores(self):
        """A symbol with aggregated scores should produce a ResearchReport."""
        now = datetime.now(UTC)
        agg = SentimentAggregator()
        agg.add_scores("AAPL", [_make_result(score=0.7, magnitude=0.8, timestamp=now)])

        bridge = SentimentBridge(aggregator=agg)
        reports = bridge.to_research_reports(["AAPL"])

        assert len(reports) == 1
        report = reports[0]
        assert isinstance(report, ResearchReport)
        assert report.symbol == "AAPL"
        assert report.sources == ["sentiment_pipeline"]

    def test_skips_symbol_with_no_scores(self):
        """Symbols not present in the aggregator should be skipped."""
        agg = SentimentAggregator()

        bridge = SentimentBridge(aggregator=agg)
        reports = bridge.to_research_reports(["AAPL", "GOOG"])

        assert reports == []

    def test_multiple_symbols(self):
        """Multiple symbols with scores should each produce a report."""
        now = datetime.now(UTC)
        agg = SentimentAggregator()
        agg.add_scores("AAPL", [_make_result(score=0.7, magnitude=1.0, timestamp=now)])
        agg.add_scores("GOOG", [_make_result(score=-0.3, magnitude=1.0, timestamp=now)])

        bridge = SentimentBridge(aggregator=agg)
        reports = bridge.to_research_reports(["AAPL", "GOOG"])

        assert len(reports) == 2
        symbols = {r.symbol for r in reports}
        assert symbols == {"AAPL", "GOOG"}

    def test_correct_sentiment_score_value(self):
        """The report's sentiment_score should match the aggregator's output."""
        now = datetime.now(UTC)
        agg = SentimentAggregator()
        agg.add_scores("AAPL", [_make_result(score=0.7, magnitude=0.8, timestamp=now)])

        bridge = SentimentBridge(aggregator=agg)
        reports = bridge.to_research_reports(["AAPL"])

        # With a single recent score: aggregate = score * magnitude * weight / weight
        # = 0.7 * 0.8 * 1.0 / 1.0 = 0.56
        expected_score = agg.aggregate("AAPL", now)
        assert reports[0].sentiment_score == pytest.approx(expected_score, abs=0.05)

    def test_sentiment_score_clamped_to_valid_range(self):
        """The sentiment_score should be clamped to [-1.0, 1.0]."""
        now = datetime.now(UTC)
        agg = SentimentAggregator()
        # Score of 1.0 with magnitude 1.0 gives aggregate of 1.0
        agg.add_scores("BTC", [_make_result(score=1.0, magnitude=1.0, timestamp=now)])

        bridge = SentimentBridge(aggregator=agg)
        reports = bridge.to_research_reports(["BTC"])

        assert -1.0 <= reports[0].sentiment_score <= 1.0

    def test_summary_contains_score(self):
        """The report summary should include the aggregated score."""
        now = datetime.now(UTC)
        agg = SentimentAggregator()
        agg.add_scores("AAPL", [_make_result(score=0.5, magnitude=1.0, timestamp=now)])

        bridge = SentimentBridge(aggregator=agg)
        reports = bridge.to_research_reports(["AAPL"])

        assert "sentiment score" in reports[0].summary.lower()

    def test_mixed_symbols_with_and_without_scores(self):
        """Only symbols present in the aggregator should produce reports."""
        now = datetime.now(UTC)
        agg = SentimentAggregator()
        agg.add_scores("AAPL", [_make_result(score=0.6, magnitude=1.0, timestamp=now)])
        # GOOG has no scores

        bridge = SentimentBridge(aggregator=agg)
        reports = bridge.to_research_reports(["AAPL", "GOOG"])

        assert len(reports) == 1
        assert reports[0].symbol == "AAPL"

    def test_report_has_utc_timestamp(self):
        """The report timestamp should be timezone-aware (UTC)."""
        now = datetime.now(UTC)
        agg = SentimentAggregator()
        agg.add_scores("AAPL", [_make_result(score=0.5, timestamp=now)])

        bridge = SentimentBridge(aggregator=agg)
        reports = bridge.to_research_reports(["AAPL"])

        assert reports[0].timestamp.tzinfo is not None
