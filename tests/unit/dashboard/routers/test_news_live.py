"""Tests that news router returns real data from the database."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-news-router-tests!!!")

from src.auth.tokens import create_access_token
from src.dashboard import dependencies
from src.dashboard.app import create_app
from src.db.database import Database
from src.db.models import ArticleRecord, FeedRecord, UserRecord


@pytest.fixture(autouse=True)
def reset_state():
    _clear_state()
    yield
    _clear_state()


def _clear_state():
    s = dependencies.state
    s.portfolio = None
    s.db = None
    s.orchestrator = None
    s.executor = None
    s.risk_manager = None
    s.event_bus = None
    s.settings = None
    s.strategies = []


@pytest.fixture
async def db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    database = Database(url)
    await database.initialize()
    yield database
    await database.close()


@pytest.fixture
def settings():
    from src.core.config import Settings

    return Settings.for_testing()


@pytest.fixture
async def auth_headers(db: Database, settings):
    user = UserRecord(email="news@example.com", hashed_password="h", name="News")
    await db.create_user(user)
    token = create_access_token(user_id=user.id, secret=settings.auth.jwt_secret_key)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client(db, settings):
    app = create_app(db=db, settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seed_data(db: Database):
    """Insert a feed and articles into the test DB."""
    feed = FeedRecord(
        name="Test Feed",
        url="https://example.com/rss",
        feed_type="rss",
        category="markets",
    )
    await db.save_feed(feed)

    article = ArticleRecord(
        content_hash="abc123",
        title="Stock Market Rallies",
        body="Markets are up today.",
        source="Test Feed",
        url="https://example.com/article1",
        published_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC),
        feed_id=feed.id,
        symbols=["SPY", "QQQ"],
    )
    await db.save_article(article)

    article2 = ArticleRecord(
        content_hash="def456",
        title="Tech Sector Update",
        body="Tech stocks are mixed.",
        source="Test Feed",
        url="https://example.com/article2",
        published_at=datetime(2026, 2, 21, 12, 0, 0, tzinfo=UTC),
        feed_id=feed.id,
        symbols=["QQQ", "AAPL"],
    )
    await db.save_article(article2)
    return {"feed": feed, "articles": [article, article2]}


class TestNewsRouterLive:
    async def test_feeds_returns_real_data(
        self, client: AsyncClient, auth_headers: dict, seed_data, db
    ):
        resp = await client.get("/api/news/feeds", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "feeds" in data
        assert len(data["feeds"]) >= 1
        assert data["feeds"][0]["name"] == "Test Feed"

    async def test_articles_returns_articles_for_symbol(
        self, client: AsyncClient, auth_headers: dict, seed_data, db
    ):
        resp = await client.get(
            "/api/news/articles?symbol=SPY", headers=auth_headers
        )
        assert resp.status_code == 200
        articles = resp.json()
        assert len(articles) >= 1
        assert articles[0]["title"] == "Stock Market Rallies"

    async def test_articles_without_symbol_returns_recent(
        self, client: AsyncClient, auth_headers: dict, seed_data, db
    ):
        resp = await client.get("/api/news/articles", headers=auth_headers)
        assert resp.status_code == 200
        articles = resp.json()
        assert len(articles) >= 2

    async def test_news_status_returns_feed_count(
        self, client: AsyncClient, auth_headers: dict, seed_data, db
    ):
        resp = await client.get("/api/news/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["feed_count"] >= 1
        assert "healthy" in data
