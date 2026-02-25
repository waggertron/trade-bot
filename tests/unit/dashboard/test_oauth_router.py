"""Tests for OAuth API endpoints with mocked providers."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-oauth-router-tests")

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


class TestOAuthRedirect:
    async def test_unsupported_provider_returns_400(self, client: AsyncClient):
        resp = await client.get("/api/auth/oauth/twitter", params={"redirect_uri": "http://x"})
        assert resp.status_code == 400

    async def test_google_redirect_returns_redirect_url(self, client: AsyncClient):
        # The redirect endpoint should return a URL to redirect to
        resp = await client.get(
            "/api/auth/oauth/google",
            params={"redirect_uri": "http://localhost:3000/auth/callback/google"},
            follow_redirects=False,
        )
        # Should be 200 with authorize_url or a 307 redirect
        assert resp.status_code in (200, 307)


class TestOAuthCallback:
    async def test_callback_creates_new_user(self, client: AsyncClient, db: Database):
        mock_token = {"access_token": "mock-token", "token_type": "bearer"}
        mock_userinfo = {
            "sub": "google-12345",
            "email": "newuser@gmail.com",
            "name": "New User",
        }
        with patch("src.dashboard.routers.oauth._fetch_oauth_user_info", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = ("google-12345", "newuser@gmail.com", "New User")
            resp = await client.post("/api/auth/oauth/google/callback", json={
                "code": "mock-auth-code",
                "redirect_uri": "http://localhost:3000/auth/callback/google",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "newuser@gmail.com"
        assert data["is_new_user"] is True

    async def test_callback_links_to_existing_user_by_email(self, client: AsyncClient, db: Database):
        # Pre-register a user with email/password
        await client.post("/api/auth/register", json={
            "email": "existing@gmail.com", "password": "Pass123!", "name": "Existing",
        })
        with patch("src.dashboard.routers.oauth._fetch_oauth_user_info", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = ("google-99", "existing@gmail.com", "Existing")
            resp = await client.post("/api/auth/oauth/google/callback", json={
                "code": "mock-code",
                "redirect_uri": "http://localhost:3000/auth/callback/google",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_new_user"] is False
        assert data["user"]["email"] == "existing@gmail.com"

    async def test_callback_returns_existing_linked_user(self, client: AsyncClient, db: Database):
        # First OAuth login creates user
        with patch("src.dashboard.routers.oauth._fetch_oauth_user_info", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = ("gh-555", "dev@github.com", "Dev")
            resp1 = await client.post("/api/auth/oauth/github/callback", json={
                "code": "code1", "redirect_uri": "http://localhost:3000/auth/callback/github",
            })
        user_id_1 = resp1.json()["user"]["id"]

        # Second OAuth login returns same user
        with patch("src.dashboard.routers.oauth._fetch_oauth_user_info", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = ("gh-555", "dev@github.com", "Dev")
            resp2 = await client.post("/api/auth/oauth/github/callback", json={
                "code": "code2", "redirect_uri": "http://localhost:3000/auth/callback/github",
            })
        user_id_2 = resp2.json()["user"]["id"]
        assert user_id_1 == user_id_2
        assert resp2.json()["is_new_user"] is False

    async def test_callback_unsupported_provider_returns_400(self, client: AsyncClient):
        resp = await client.post("/api/auth/oauth/twitter/callback", json={
            "code": "code", "redirect_uri": "http://example.com",
        })
        assert resp.status_code == 400
