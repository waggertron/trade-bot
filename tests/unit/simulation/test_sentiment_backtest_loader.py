"""Tests for SentimentBacktestLoader — lookahead-free historical sentiment replay."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.simulation.sentiment_backtest import SentimentBacktestLoader


def _dt(year: int, month: int, day: int, hour: int = 0) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


def _make_mock_db(rows: list[tuple]) -> MagicMock:
    """Build a mock Database whose get_scores_as_of returns the given rows."""
    db = MagicMock()
    db.get_scores_as_of = AsyncMock(return_value=rows)
    return db


class TestGetResearchAt:
    @pytest.mark.asyncio
    async def test_get_research_at_returns_empty_before_any_articles(self):
        db = _make_mock_db([])
        loader = SentimentBacktestLoader(db, ["AAPL"])
        await loader.load()

        reports = loader.get_research_at(_dt(2026, 1, 1))
        assert reports == []

    @pytest.mark.asyncio
    async def test_get_research_at_returns_report_after_articles_published(self):
        rows = [
            ("AAPL", 0.7, 0.9, _dt(2026, 1, 10)),
        ]
        db = _make_mock_db(rows)
        loader = SentimentBacktestLoader(db, ["AAPL"])
        await loader.load()

        reports = loader.get_research_at(_dt(2026, 1, 15))
        assert len(reports) == 1
        assert reports[0].symbol == "AAPL"
        assert reports[0].sentiment_score != 0.0

    @pytest.mark.asyncio
    async def test_no_lookahead_bias_future_articles_excluded(self):
        rows = [
            ("AAPL", 0.7, 0.9, _dt(2026, 1, 10)),
            ("AAPL", 0.9, 1.0, _dt(2026, 1, 20)),  # published after tick time
        ]
        db = _make_mock_db(rows)
        loader = SentimentBacktestLoader(db, ["AAPL"])
        await loader.load()

        # Ask for research as of Jan 15 — should NOT see the Jan 20 article
        reports_early = loader.get_research_at(_dt(2026, 1, 15))
        reports_late = loader.get_research_at(_dt(2026, 1, 25))

        assert len(reports_early) == 1
        assert len(reports_late) == 1
        # The score at Jan 25 should be higher (includes the bullish Jan 20 article)
        assert reports_late[0].sentiment_score >= reports_early[0].sentiment_score

    @pytest.mark.asyncio
    async def test_coverage_returns_correct_date_range(self):
        rows = [
            ("AAPL", 0.5, 0.8, _dt(2026, 1, 5)),
            ("AAPL", 0.6, 0.9, _dt(2026, 1, 15)),
            ("MSFT", 0.4, 0.7, _dt(2026, 1, 10)),
        ]
        db = _make_mock_db(rows)
        loader = SentimentBacktestLoader(db, ["AAPL", "MSFT"])
        await loader.load()

        cov = loader.coverage
        assert cov["total_articles"] == 3
        assert cov["min_date"] == _dt(2026, 1, 5)
        assert cov["max_date"] == _dt(2026, 1, 15)

    @pytest.mark.asyncio
    async def test_cache_returns_same_object_for_same_calendar_day(self):
        rows = [
            ("AAPL", 0.5, 0.8, _dt(2026, 1, 10)),
        ]
        db = _make_mock_db(rows)
        loader = SentimentBacktestLoader(db, ["AAPL"])
        await loader.load()

        # Different hours, same calendar date
        reports_morning = loader.get_research_at(_dt(2026, 1, 15, 9))
        reports_afternoon = loader.get_research_at(_dt(2026, 1, 15, 16))
        assert reports_morning is reports_afternoon
