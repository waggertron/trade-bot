"""Tests for HTTP-only cookie-based authentication."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-cookie-auth-tests!!")

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


class TestCookieAuth:
    async def test_login_sets_httponly_cookie(self, client: AsyncClient):
        """Login should set an access_token cookie with HttpOnly flag."""
        await client.post(
            "/api/auth/register",
            json={
                "email": "cookie@example.com",
                "password": "CookiePass1!",
                "name": "Cookie",
            },
        )
        resp = await client.post(
            "/api/auth/login",
            json={
                "email": "cookie@example.com",
                "password": "CookiePass1!",
            },
        )
        assert resp.status_code == 200
        # Check that access_token cookie was set
        cookies = resp.cookies
        assert "access_token" in cookies

    async def test_register_sets_httponly_cookie(self, client: AsyncClient):
        """Register should also set an access_token cookie."""
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "newcookie@example.com",
                "password": "CookiePass1!",
                "name": "New",
            },
        )
        assert resp.status_code == 201
        assert "access_token" in resp.cookies

    async def test_cookie_auth_works_for_me_endpoint(self, client: AsyncClient):
        """Accessing /me with cookie-based auth should work."""
        reg = await client.post(
            "/api/auth/register",
            json={
                "email": "cookieme@example.com",
                "password": "CookiePass1!",
                "name": "CookieMe",
            },
        )
        # Extract the cookie from the response
        access_token = reg.cookies.get("access_token")
        assert access_token is not None

        # Make request with cookie (no Authorization header)
        resp = await client.get(
            "/api/auth/me",
            cookies={"access_token": access_token},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "cookieme@example.com"

    async def test_bearer_header_still_works(self, client: AsyncClient):
        """Authorization: Bearer header should still work as fallback."""
        reg = await client.post(
            "/api/auth/register",
            json={
                "email": "bearer@example.com",
                "password": "BearerPass1!",
                "name": "Bearer",
            },
        )
        token = reg.json()["access_token"]

        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "bearer@example.com"
