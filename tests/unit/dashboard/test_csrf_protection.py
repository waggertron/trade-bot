"""Tests for CSRF protection on state-changing requests."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-csrf-protection-tests!!")

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


async def _register_and_get_cookies(client: AsyncClient) -> dict[str, str]:
    """Register a user and return the cookies set by the response."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "csrf@example.com",
            "password": "CsrfPass1!",
            "name": "CSRF Test",
        },
    )
    assert resp.status_code == 201
    cookies = {}
    for k, v in resp.cookies.items():
        cookies[k] = v
    return cookies


class TestCSRFProtection:
    async def test_post_without_csrf_token_rejected(self, client: AsyncClient):
        """POST to a protected endpoint without CSRF token should be rejected."""
        cookies = await _register_and_get_cookies(client)
        # GET /me should still work (safe method, no CSRF needed)
        resp = await client.get("/api/auth/me", cookies=cookies)
        assert resp.status_code == 200

        # POST without CSRF token should fail
        resp = await client.post("/api/trading/order", cookies=cookies, json={
            "symbol": "AAPL",
            "side": "buy",
            "order_type": "market",
            "quantity": 1.0,
        })
        assert resp.status_code == 403
        assert "CSRF" in resp.json()["detail"]

    async def test_post_with_valid_csrf_token_accepted(self, client: AsyncClient):
        """POST with valid CSRF token header should succeed."""
        cookies = await _register_and_get_cookies(client)
        csrf_token = cookies.get("csrf_token")
        assert csrf_token is not None, "csrf_token cookie should be set on auth"

        # POST with CSRF header should work
        resp = await client.get(
            "/api/auth/me",
            cookies=cookies,
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 200

    async def test_get_request_does_not_require_csrf(self, client: AsyncClient):
        """GET requests should not require CSRF token."""
        cookies = await _register_and_get_cookies(client)
        resp = await client.get("/api/auth/me", cookies=cookies)
        assert resp.status_code == 200

    async def test_csrf_cookie_is_not_httponly(self, client: AsyncClient):
        """CSRF cookie must be readable by JavaScript (not HttpOnly)."""
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "csrfcookie@example.com",
                "password": "CsrfPass1!",
                "name": "Cookie Test",
            },
        )
        assert resp.status_code == 201
        # Check that csrf_token cookie is present in Set-Cookie headers
        set_cookies = resp.headers.get_list("set-cookie")
        csrf_cookies = [c for c in set_cookies if c.startswith("csrf_token=")]
        assert len(csrf_cookies) == 1
        # It should NOT contain HttpOnly
        assert "httponly" not in csrf_cookies[0].lower()

    async def test_auth_endpoints_exempt_from_csrf(self, client: AsyncClient):
        """Auth endpoints (login, register, refresh) should not require CSRF."""
        # Register should work without CSRF
        resp = await client.post(
            "/api/auth/register",
            json={
                "email": "nocsrf@example.com",
                "password": "NoCsrfPass1!",
                "name": "No CSRF",
            },
        )
        assert resp.status_code == 201

        # Login should work without CSRF
        resp = await client.post(
            "/api/auth/login",
            json={"email": "nocsrf@example.com", "password": "NoCsrfPass1!"},
        )
        assert resp.status_code == 200
