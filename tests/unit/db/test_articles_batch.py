"""Tests that article queries batch-load symbols instead of N+1."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.db.database import Database
from src.db.models import ArticleRecord


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
async def seeded_db(db: Database):
    """Seed DB with articles tagged to multiple symbols."""
    for i in range(5):
        article = ArticleRecord(
            content_hash=f"hash-{i}",
            title=f"Article {i}",
            body=f"Body {i}",
            source="test-source",
            url=f"https://example.com/{i}",
            published_at=datetime(2026, 1, 1 + i, tzinfo=UTC),
            fetched_at=datetime(2026, 1, 1 + i, tzinfo=UTC),
            symbols=["AAPL", "GOOGL"] if i % 2 == 0 else ["AAPL"],
        )
        await db.save_article(article)
    return db


class TestArticlesBatch:
    async def test_get_articles_for_symbol_returns_correct_count(self, seeded_db: Database):
        """All 5 articles are tagged with AAPL."""
        articles = await seeded_db.get_articles_for_symbol("AAPL", limit=100)
        assert len(articles) == 5

    async def test_get_articles_for_symbol_includes_all_symbols(self, seeded_db: Database):
        """Each article should include ALL its symbols, not just the queried one."""
        articles = await seeded_db.get_articles_for_symbol("AAPL", limit=100)
        # Articles 0, 2, 4 have both AAPL and GOOGL
        multi_symbol = [a for a in articles if len(a.symbols) > 1]
        assert len(multi_symbol) == 3
        for a in multi_symbol:
            assert "AAPL" in a.symbols
            assert "GOOGL" in a.symbols

    async def test_get_articles_does_not_query_per_row(self, seeded_db: Database):
        """Verify _get_article_symbols is NOT called per row (N+1 pattern).

        After batching, it should not be called at all — replaced by batch loading.
        """
        from unittest.mock import AsyncMock, patch

        with patch.object(seeded_db, "_get_article_symbols", new_callable=AsyncMock) as mock_get:
            articles = await seeded_db.get_articles_for_symbol("AAPL", limit=100)

        # With N+1, this would be called 5 times (once per article)
        # With batch loading, it should not be called at all
        assert mock_get.call_count == 0, (
            f"_get_article_symbols called {mock_get.call_count} times — N+1 detected"
        )
        # Results should still be populated (from batch query)
        assert len(articles) == 5

    async def test_list_articles_does_not_query_per_row(self, seeded_db: Database):
        """list_articles should also use batch loading, not N+1."""
        from unittest.mock import AsyncMock, patch

        with patch.object(seeded_db, "_get_article_symbols", new_callable=AsyncMock) as mock_get:
            articles = await seeded_db.list_articles(limit=100)

        assert mock_get.call_count == 0, (
            f"_get_article_symbols called {mock_get.call_count} times — N+1 detected"
        )
        assert len(articles) == 5
