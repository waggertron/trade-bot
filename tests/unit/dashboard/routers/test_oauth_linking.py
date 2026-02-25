"""Tests that OAuth account linking requires email verification."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-oauth-linking-test!")

from src.dashboard import dependencies
from src.dashboard.app import create_app
from src.dashboard.routers.oauth import _generate_state_token
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


class TestOAuthLinkingRequiresVerification:
    async def test_unverified_user_blocks_oauth_linking(self, client: AsyncClient, db: Database):
        """If an existing user has unverified email, OAuth should reject with 409
        and instruct user to verify email first."""
        # Register a user (is_verified defaults to False)
        await client.post(
            "/api/auth/register",
            json={
                "email": "unverified@gmail.com",
                "password": "Pass123!",
                "name": "Unverified",
            },
        )

        # OAuth login with same email should be rejected
        valid_state = _generate_state_token()
        with patch(
            "src.dashboard.routers.oauth._fetch_oauth_user_info",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = (
                "google-999",
                "unverified@gmail.com",
                "Unverified",
            )
            resp = await client.post(
                "/api/auth/oauth/google/callback",
                json={
                    "code": "mock-code",
                    "redirect_uri": "http://localhost:3000/callback",
                    "state": valid_state,
                },
            )

        assert resp.status_code == 409
        assert "verify" in resp.json()["detail"].lower()

    async def test_verified_user_gets_linked(self, client: AsyncClient, db: Database):
        """If an existing user has verified email, OAuth should link to them."""
        # Create and verify a user
        user = UserRecord(
            email="verified@gmail.com",
            hashed_password="hashed",
            name="Verified",
            is_verified=True,
        )
        await db.create_user(user)

        # OAuth login with same email SHOULD link
        valid_state = _generate_state_token()
        with patch(
            "src.dashboard.routers.oauth._fetch_oauth_user_info",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = (
                "google-888",
                "verified@gmail.com",
                "Verified",
            )
            resp = await client.post(
                "/api/auth/oauth/google/callback",
                json={
                    "code": "mock-code",
                    "redirect_uri": "http://localhost:3000/callback",
                    "state": valid_state,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_new_user"] is False
        assert data["user"]["id"] == user.id
