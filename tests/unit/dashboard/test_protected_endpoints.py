"""Tests that user-data endpoints require auth and return user-scoped data."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-protected-tests")

from src.dashboard import dependencies
from src.dashboard.app import create_app
from src.db.database import Database
from src.db.models import SignalRecord, TradeRecord


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
async def client(db, settings):
    app = create_app(db=db, settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _register_and_get_token(client: AsyncClient, email: str) -> tuple[str, str]:
    """Register user and return (user_id, access_token)."""
    resp = await client.post("/api/auth/register", json={
        "email": email, "password": "TestPass1!", "name": "Test",
    })
    data = resp.json()
    return data["user"]["id"], data["access_token"]


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestTradesEndpointAuth:
    async def test_list_trades_returns_401_without_token(self, client: AsyncClient):
        resp = await client.get("/api/trades/")
        assert resp.status_code == 401

    async def test_get_trade_returns_401_without_token(self, client: AsyncClient):
        resp = await client.get("/api/trades/some-id")
        assert resp.status_code == 401

    async def test_list_trades_returns_own_data(self, client: AsyncClient, db: Database):
        uid_a, token_a = await _register_and_get_token(client, "alice@test.com")
        uid_b, token_b = await _register_and_get_token(client, "bob@test.com")

        # Insert trades for both users
        await db.save_trade(TradeRecord(
            symbol="AAPL", side="buy", quantity="10", price="100",
            commission="1", strategy="momentum", paper=True,
            timestamp=datetime.now(timezone.utc), user_id=uid_a,
        ))
        await db.save_trade(TradeRecord(
            symbol="MSFT", side="buy", quantity="5", price="200",
            commission="1", strategy="momentum", paper=True,
            timestamp=datetime.now(timezone.utc), user_id=uid_b,
        ))

        # Alice only sees her trade
        resp = await client.get("/api/trades/", headers=_auth_header(token_a))
        assert resp.status_code == 200
        trades = resp.json()
        assert len(trades) == 1
        assert trades[0]["symbol"] == "AAPL"

        # Bob only sees his trade
        resp = await client.get("/api/trades/", headers=_auth_header(token_b))
        assert resp.status_code == 200
        trades = resp.json()
        assert len(trades) == 1
        assert trades[0]["symbol"] == "MSFT"


class TestSignalsEndpointAuth:
    async def test_list_signals_returns_401_without_token(self, client: AsyncClient):
        resp = await client.get("/api/signals/")
        assert resp.status_code == 401

    async def test_latest_signals_returns_401_without_token(self, client: AsyncClient):
        resp = await client.get("/api/signals/latest")
        assert resp.status_code == 401

    async def test_list_signals_returns_own_data(self, client: AsyncClient, db: Database):
        uid_a, token_a = await _register_and_get_token(client, "alice@test.com")
        uid_b, token_b = await _register_and_get_token(client, "bob@test.com")

        await db.save_signal(SignalRecord(
            symbol="AAPL", direction="buy", confidence=0.9,
            strategy="momentum", reasoning="test",
            timestamp=datetime.now(timezone.utc), user_id=uid_a,
        ))
        await db.save_signal(SignalRecord(
            symbol="MSFT", direction="sell", confidence=0.7,
            strategy="sentiment", reasoning="test",
            timestamp=datetime.now(timezone.utc), user_id=uid_b,
        ))

        resp = await client.get("/api/signals/", headers=_auth_header(token_a))
        assert resp.status_code == 200
        signals = resp.json()
        assert len(signals) == 1
        assert signals[0]["symbol"] == "AAPL"


class TestOtherEndpointsRequireAuth:
    """Verify other data endpoints return 401 without auth."""

    @pytest.mark.parametrize("path", [
        "/api/portfolio/",
        "/api/portfolio/positions",
        "/api/strategies/",
        "/api/strategies/status",
        "/api/analytics/attribution",
        "/api/risk/status",
        "/api/config/",
        "/api/trading/orders",
    ])
    async def test_returns_401(self, client: AsyncClient, path: str):
        resp = await client.get(path)
        assert resp.status_code == 401

    async def test_health_stays_public(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
