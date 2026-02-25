"""Tests that analytics router returns data from DB trade records."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-analytics-router-test!!")

from src.auth.tokens import create_access_token
from src.dashboard import dependencies
from src.dashboard.app import create_app
from src.db.database import Database
from src.db.models import TradeRecord, UserRecord


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
    s.ml_model = None


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
    user = UserRecord(email="analytics@example.com", hashed_password="h", name="Analytics")
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
async def seed_trades(db: Database):
    """Insert trade records for attribution."""
    trades = [
        TradeRecord(
            symbol="AAPL",
            side="buy",
            quantity="10",
            price="150.00",
            commission="1.00",
            strategy="momentum",
            paper=True,
            timestamp=datetime(2026, 2, 20, 10, 0, 0, tzinfo=UTC),
        ),
        TradeRecord(
            symbol="AAPL",
            side="sell",
            quantity="10",
            price="155.00",
            commission="1.00",
            strategy="momentum",
            paper=True,
            timestamp=datetime(2026, 2, 21, 10, 0, 0, tzinfo=UTC),
        ),
        TradeRecord(
            symbol="GOOGL",
            side="buy",
            quantity="5",
            price="140.00",
            commission="1.00",
            strategy="mean_reversion",
            paper=True,
            timestamp=datetime(2026, 2, 20, 11, 0, 0, tzinfo=UTC),
        ),
        TradeRecord(
            symbol="GOOGL",
            side="sell",
            quantity="5",
            price="138.00",
            commission="1.00",
            strategy="mean_reversion",
            paper=True,
            timestamp=datetime(2026, 2, 21, 11, 0, 0, tzinfo=UTC),
        ),
    ]
    for t in trades:
        await db.save_trade(t)
    return trades


class TestAnalyticsLive:
    async def test_attribution_returns_strategies_from_db(
        self, client: AsyncClient, auth_headers: dict, seed_trades
    ):
        """Attribution should build report from DB trade records."""
        resp = await client.get("/api/analytics/attribution", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "strategies" in data
        assert "momentum" in data["strategies"]
        assert data["strategies"]["momentum"]["total_trades"] >= 1

    async def test_attribution_empty_when_no_trades(self, client: AsyncClient, auth_headers: dict):
        """Attribution with no trades returns empty strategies."""
        resp = await client.get("/api/analytics/attribution", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["strategies"] == {}
        assert data["total_pnl"] == 0.0
