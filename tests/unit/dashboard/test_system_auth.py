"""Tests that system control endpoints require authentication."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-system-auth-tests!!")

from src.auth.tokens import create_access_token
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


@pytest.fixture
async def auth_headers(db: Database, settings):
    user = UserRecord(
        email="admin@example.com",
        hashed_password="hashed",
        name="Admin",
    )
    await db.create_user(user)
    token = create_access_token(
        user_id=user.id,
        secret=settings.auth.jwt_secret_key,
    )
    return {"Authorization": f"Bearer {token}"}


class TestSystemEndpointsRequireAuth:
    async def test_kill_without_auth_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/kill")
        assert resp.status_code == 401

    async def test_pause_without_auth_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/pause")
        assert resp.status_code == 401

    async def test_resume_without_auth_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/resume")
        assert resp.status_code == 401

    async def test_system_status_without_auth_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/system/status")
        assert resp.status_code == 401

    async def test_health_is_public(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200

    async def test_kill_with_auth_succeeds(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/kill", headers=auth_headers)
        assert resp.status_code == 200

    async def test_system_status_with_auth_succeeds(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/system/status", headers=auth_headers)
        assert resp.status_code == 200
