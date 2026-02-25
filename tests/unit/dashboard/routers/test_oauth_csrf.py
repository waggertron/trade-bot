"""Tests for OAuth CSRF state token protection."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-oauth-csrf-tests!!")

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


class TestOAuthStateToken:
    async def test_redirect_includes_state_param(self, client: AsyncClient):
        """The redirect endpoint should return a state token in the authorize_url."""
        resp = await client.get(
            "/api/auth/oauth/google",
            params={"redirect_uri": "http://localhost:3000/auth/callback/google"},
            follow_redirects=False,
        )
        # Skip if provider not configured (503)
        if resp.status_code == 503:
            pytest.skip("OAuth provider not configured")
        assert resp.status_code == 200
        data = resp.json()
        assert "state" in data
        assert len(data["state"]) > 0
        assert "state=" in data["authorize_url"]

    async def test_callback_rejects_missing_state(self, client: AsyncClient):
        """Callback without state param should be rejected."""
        with patch(
            "src.dashboard.routers.oauth._fetch_oauth_user_info",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = ("google-123", "test@gmail.com", "Test")
            resp = await client.post(
                "/api/auth/oauth/google/callback",
                json={
                    "code": "mock-code",
                    "redirect_uri": "http://localhost:3000/auth/callback/google",
                },
            )
        assert resp.status_code == 400
        assert "state" in resp.json()["detail"].lower()

    async def test_callback_rejects_invalid_state(self, client: AsyncClient):
        """Callback with a bad state param should be rejected."""
        with patch(
            "src.dashboard.routers.oauth._fetch_oauth_user_info",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = ("google-123", "test@gmail.com", "Test")
            resp = await client.post(
                "/api/auth/oauth/google/callback",
                json={
                    "code": "mock-code",
                    "redirect_uri": "http://localhost:3000/auth/callback/google",
                    "state": "forged-state-token",
                },
            )
        assert resp.status_code == 400
        assert "state" in resp.json()["detail"].lower()
