"""Tests for auth API endpoints: register, login, refresh, me."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Set JWT secret before any app imports
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-auth-router-tests!")

from src.dashboard import dependencies
from src.dashboard.app import create_app
from src.db.database import Database


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


class TestRegister:
    async def test_register_returns_tokens(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "alice@example.com",
                "password": "StrongPass123!",
                "name": "Alice",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "alice@example.com"
        assert data["user"]["name"] == "Alice"
        assert "hashed_password" not in data["user"]

    async def test_register_duplicate_email_returns_409(self, client: AsyncClient):
        payload = {"email": "dup@example.com", "password": "Pass123!", "name": "Dup"}
        await client.post("/api/auth/register", json=payload)
        resp = await client.post("/api/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_register_missing_password_returns_422(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "bad@example.com",
            },
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_login_returns_tokens(self, client: AsyncClient):
        await client.post(
            "/api/auth/register",
            json={
                "email": "bob@example.com",
                "password": "Secret99!",
                "name": "Bob",
            },
        )
        resp = await client.post(
            "/api/auth/login",
            json={
                "email": "bob@example.com",
                "password": "Secret99!",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_wrong_password_returns_401(self, client: AsyncClient):
        await client.post(
            "/api/auth/register",
            json={
                "email": "bob@example.com",
                "password": "Secret99!",
                "name": "Bob",
            },
        )
        resp = await client.post(
            "/api/auth/login",
            json={
                "email": "bob@example.com",
                "password": "WrongPass",
            },
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_email_returns_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth/login",
            json={
                "email": "ghost@example.com",
                "password": "Pass123!",
            },
        )
        assert resp.status_code == 401


class TestRefresh:
    async def test_refresh_returns_new_access_token(self, client: AsyncClient):
        reg = await client.post(
            "/api/auth/register",
            json={
                "email": "carol@example.com",
                "password": "Refresh1!",
                "name": "Carol",
            },
        )
        refresh_token = reg.json()["refresh_token"]
        resp = await client.post(
            "/api/auth/refresh",
            json={
                "refresh_token": refresh_token,
            },
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_refresh_with_access_token_returns_401(self, client: AsyncClient):
        reg = await client.post(
            "/api/auth/register",
            json={
                "email": "carol@example.com",
                "password": "Refresh1!",
                "name": "Carol",
            },
        )
        access_token = reg.json()["access_token"]
        resp = await client.post(
            "/api/auth/refresh",
            json={
                "refresh_token": access_token,
            },
        )
        assert resp.status_code == 401

    async def test_refresh_with_invalid_token_returns_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/auth/refresh",
            json={
                "refresh_token": "garbage",
            },
        )
        assert resp.status_code == 401


class TestMe:
    async def test_me_returns_current_user(self, client: AsyncClient):
        reg = await client.post(
            "/api/auth/register",
            json={
                "email": "dave@example.com",
                "password": "MyPass1!",
                "name": "Dave",
            },
        )
        token = reg.json()["access_token"]
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "dave@example.com"
        assert "hashed_password" not in resp.json()

    async def test_me_without_token_returns_401(self, client: AsyncClient):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_me_with_invalid_token_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer bad-token"},
        )
        assert resp.status_code == 401


class TestLogout:
    async def test_logout_revokes_token(self, client: AsyncClient):
        reg = await client.post(
            "/api/auth/register",
            json={
                "email": "logout@example.com",
                "password": "Logout1!",
                "name": "Logout",
            },
        )
        token = reg.json()["access_token"]

        # Logout should succeed
        resp = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

        # Token should now be rejected
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    async def test_logout_without_token_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/auth/logout")
        assert resp.status_code == 401


class TestUpdateMe:
    async def test_update_name(self, client: AsyncClient):
        reg = await client.post(
            "/api/auth/register",
            json={
                "email": "eve@example.com",
                "password": "Update1!",
                "name": "Eve",
            },
        )
        token = reg.json()["access_token"]
        resp = await client.put(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Evelyn"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Evelyn"
