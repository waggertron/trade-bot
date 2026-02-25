"""Tests for Database.get_scores_as_of() — lookahead-free sentiment query."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.db.database import Database
from src.db.models import ArticleRecord, SentimentScoreRecord


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


def _make_article(content_hash: str, published_at: datetime, symbols: list[str]) -> ArticleRecord:
    return ArticleRecord(
        content_hash=content_hash,
        title=f"Article {content_hash}",
        source="rss",
        published_at=published_at,
        symbols=symbols,
    )


def _make_score(article_id: str, score: float = 0.5, analyzer: str = "ollama") -> SentimentScoreRecord:
    return SentimentScoreRecord(
        article_id=article_id,
        score=score,
        magnitude=0.8,
        reasoning="test",
        analyzer=analyzer,
    )


class TestGetScoresAsOf:
    @pytest.mark.asyncio
    async def test_returns_only_articles_published_before_cutoff(self, db):
        early = _make_article("h1", datetime(2026, 1, 10, tzinfo=timezone.utc), ["AAPL"])
        await db.save_article(early)
        await db.save_score(_make_score(early.id, score=0.6))

        cutoff = datetime(2026, 1, 15, tzinfo=timezone.utc)
        rows = await db.get_scores_as_of(["AAPL"], cutoff)

        assert len(rows) == 1
        symbol, score, magnitude, published_at = rows[0]
        assert symbol == "AAPL"
        assert score == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_excludes_articles_published_after_cutoff(self, db):
        early = _make_article("h1", datetime(2026, 1, 10, tzinfo=timezone.utc), ["AAPL"])
        late = _make_article("h2", datetime(2026, 1, 20, tzinfo=timezone.utc), ["AAPL"])
        await db.save_article(early)
        await db.save_article(late)
        await db.save_score(_make_score(early.id, score=0.6))
        await db.save_score(_make_score(late.id, score=0.9))

        cutoff = datetime(2026, 1, 15, tzinfo=timezone.utc)
        rows = await db.get_scores_as_of(["AAPL"], cutoff)

        assert len(rows) == 1
        assert rows[0][1] == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_articles_before_cutoff(self, db):
        late = _make_article("h1", datetime(2026, 2, 1, tzinfo=timezone.utc), ["AAPL"])
        await db.save_article(late)
        await db.save_score(_make_score(late.id))

        cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = await db.get_scores_as_of(["AAPL"], cutoff)

        assert rows == []

    @pytest.mark.asyncio
    async def test_published_at_returned_as_datetime_not_string(self, db):
        article = _make_article("h1", datetime(2026, 1, 10, tzinfo=timezone.utc), ["AAPL"])
        await db.save_article(article)
        await db.save_score(_make_score(article.id))

        cutoff = datetime(2026, 1, 15, tzinfo=timezone.utc)
        rows = await db.get_scores_as_of(["AAPL"], cutoff)

        assert len(rows) == 1
        published_at = rows[0][3]
        assert isinstance(published_at, datetime), f"expected datetime, got {type(published_at)}"
        assert published_at.date() == datetime(2026, 1, 10).date()

    @pytest.mark.asyncio
    async def test_filters_by_analyzer_when_provided(self, db):
        article = _make_article("h1", datetime(2026, 1, 10, tzinfo=timezone.utc), ["AAPL"])
        await db.save_article(article)
        await db.save_score(_make_score(article.id, score=0.5, analyzer="ollama"))
        await db.save_score(_make_score(article.id, score=0.8, analyzer="finbert"))

        cutoff = datetime(2026, 1, 15, tzinfo=timezone.utc)
        rows = await db.get_scores_as_of(["AAPL"], cutoff, analyzer="finbert")

        assert len(rows) == 1
        assert rows[0][1] == pytest.approx(0.8)
