"""Integration tests for Database against the configured backend (SQLite or Postgres).

When DATABASE_URL is set (e.g. in CI with Postgres), these tests exercise the full
CRUD cycle against a real Postgres database. Locally they fall back to SQLite.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.db.database import Database
from src.db.models import (
    ArticleRecord,
    FeedRecord,
    SignalRecord,
    TradeRecord,
    UserRecord,
    UserSettingsRecord,
)


@pytest.fixture
async def db(db_url):
    """Create a Database using the db_url fixture (Postgres in CI, SQLite locally)."""
    database = Database(db_url)
    await database.initialize()
    yield database
    await database.close()


class TestDatabaseCRUD:
    """Exercises core CRUD operations against the configured DB backend."""

    async def test_user_create_and_retrieve(self, db: Database):
        user = UserRecord(email="pgtest@example.com", hashed_password="hash", name="PG Test")
        await db.create_user(user)
        fetched = await db.get_user_by_email("pgtest@example.com")
        assert fetched is not None
        assert fetched.email == "pgtest@example.com"
        assert fetched.name == "PG Test"

    async def test_user_settings_round_trip(self, db: Database):
        user = UserRecord(email="settings@example.com", hashed_password="h", name="S")
        await db.create_user(user)

        settings = UserSettingsRecord(user_id=user.id, mode="paper", strategy_weights='{"mom": 1}')
        await db.save_user_settings(settings)

        fetched = await db.get_user_settings(user.id)
        assert fetched is not None
        assert fetched.mode == "paper"
        assert fetched.strategy_weights == '{"mom": 1}'

    async def test_trade_save_and_list(self, db: Database):
        trade = TradeRecord(
            symbol="AAPL",
            side="buy",
            quantity="10",
            price="150.00",
            commission="1.00",
            strategy="momentum",
            paper=True,
            timestamp=datetime.now(UTC),
        )
        await db.save_trade(trade)
        trades = await db.list_trades(limit=10)
        assert len(trades) >= 1
        assert any(t.symbol == "AAPL" for t in trades)

    async def test_signal_save_and_list(self, db: Database):
        signal = SignalRecord(
            symbol="BTC/USD",
            direction="buy",
            confidence=0.85,
            strategy="momentum",
            reasoning="uptrend detected",
            timestamp=datetime.now(UTC),
        )
        await db.save_signal(signal)
        signals = await db.list_signals(limit=10)
        assert len(signals) >= 1
        assert any(s.symbol == "BTC/USD" for s in signals)

    async def test_feed_save_and_list(self, db: Database):
        feed = FeedRecord(
            name="Test Feed",
            url="https://example.com/rss",
            feed_type="rss",
            category="markets",
        )
        await db.save_feed(feed)
        feeds = await db.list_feeds()
        assert len(feeds) >= 1
        assert any(f.name == "Test Feed" for f in feeds)

    async def test_article_save_and_query(self, db: Database):
        article = ArticleRecord(
            content_hash="testhash123",
            title="Market Update",
            body="Markets are up today.",
            source="test",
            url="https://example.com/article",
            published_at=datetime.now(UTC),
            symbols=["AAPL", "GOOGL"],
        )
        await db.save_article(article)

        articles = await db.get_articles_for_symbol("AAPL", limit=10)
        assert len(articles) >= 1
        found = articles[0]
        assert found.title == "Market Update"
        assert "AAPL" in found.symbols
        assert "GOOGL" in found.symbols

    async def test_backtest_run_round_trip(self, db: Database):
        run_data = {
            "id": "test-run-1",
            "status": "completed",
            "config": '{"symbols": ["AAPL"]}',
            "result": '{"return_pct": 5.2}',
            "started_at": datetime.now(UTC).isoformat(),
        }
        await db.save_backtest_run(run_data)

        fetched = await db.get_backtest_run("test-run-1")
        assert fetched is not None
        assert fetched["id"] == "test-run-1"
        assert fetched["status"] == "completed"

        runs = await db.list_backtest_runs()
        assert len(runs) >= 1

    async def test_token_revocation(self, db: Database):
        jti = "test-jti-12345"
        assert await db.is_token_revoked(jti) is False

        await db.revoke_token(jti)
        assert await db.is_token_revoked(jti) is True

    async def test_health_check(self, db: Database):
        assert await db.check_health() is True
