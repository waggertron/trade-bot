"""Tests that risk router returns real data from risk manager."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-risk-router-tests!!!")

from src.auth.tokens import create_access_token
from src.core.config import RiskSettings
from src.dashboard import dependencies
from src.dashboard.app import create_app
from src.db.database import Database
from src.db.models import UserRecord


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
    user = UserRecord(email="risk@example.com", hashed_password="h", name="Risk")
    await db.create_user(user)
    token = create_access_token(user_id=user.id, secret=settings.auth.jwt_secret_key)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_risk_manager():
    rm = MagicMock()
    rm._settings = RiskSettings()
    rm._daily_pnl = -50.0
    rm._circuit_breaker = None
    return rm


@pytest.fixture
def mock_portfolio():
    portfolio = AsyncMock()
    snapshot = MagicMock()
    snapshot.total_value = 10000.0
    snapshot.positions = [MagicMock(symbol="AAPL"), MagicMock(symbol="GOOGL")]
    portfolio.get_snapshot = AsyncMock(return_value=snapshot)
    return portfolio


@pytest.fixture
async def client(db, settings, mock_risk_manager, mock_portfolio):
    app = create_app(
        db=db,
        settings=settings,
        risk_manager=mock_risk_manager,
        portfolio_manager=mock_portfolio,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestRiskLive:
    async def test_status_returns_settings(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/risk/status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "max_position_pct" in data
        assert "daily_loss_limit_pct" in data

    async def test_drawdown_returns_real_values(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/risk/drawdown", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["daily_pct"] > 0  # We set _daily_pnl = -50
        assert data["positions_used"] == 2

    async def test_regime_returns_value(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/risk/regime", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "regime" in data
        assert isinstance(data["regime"], str)

    async def test_status_without_risk_manager(self, db, settings, auth_headers):
        """Without risk manager, returns error."""
        dependencies.state.risk_manager = None
        app = create_app(db=db, settings=settings)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/risk/status", headers=auth_headers)
        assert resp.status_code == 200
        assert "error" in resp.json()
