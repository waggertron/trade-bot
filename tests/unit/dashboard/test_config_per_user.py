"""Tests that config endpoints use per-user settings from DB."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-config-tests")

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


async def _register_and_get_token(client: AsyncClient, email: str) -> tuple[str, str]:
    resp = await client.post("/api/auth/register", json={
        "email": email, "password": "TestPass1!", "name": "Test",
    })
    data = resp.json()
    return data["user"]["id"], data["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestConfigModePerUser:
    async def test_get_mode_returns_user_setting(self, client: AsyncClient, db: Database):
        uid, token = await _register_and_get_token(client, "alice@test.com")
        # Save custom user setting
        from src.db.models import UserSettingsRecord
        await db.save_user_settings(UserSettingsRecord(user_id=uid, mode="live"))

        resp = await client.get("/api/config/mode", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["mode"] == "live"

    async def test_get_mode_defaults_to_paper(self, client: AsyncClient):
        _, token = await _register_and_get_token(client, "bob@test.com")
        resp = await client.get("/api/config/mode", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["mode"] == "paper"

    async def test_set_mode_persists_to_db(self, client: AsyncClient, db: Database):
        uid, token = await _register_and_get_token(client, "alice@test.com")
        resp = await client.put("/api/config/mode", json={"mode": "live"}, headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json()["mode"] == "live"

        # Verify persisted
        settings = await db.get_user_settings(uid)
        assert settings is not None
        assert settings.mode == "live"

    async def test_mode_isolated_between_users(self, client: AsyncClient):
        _, token_a = await _register_and_get_token(client, "alice@test.com")
        _, token_b = await _register_and_get_token(client, "bob@test.com")

        await client.put("/api/config/mode", json={"mode": "live"}, headers=_auth(token_a))
        # Bob still has default paper mode
        resp = await client.get("/api/config/mode", headers=_auth(token_b))
        assert resp.json()["mode"] == "paper"


class TestConfigSymbolsPerUser:
    async def test_update_symbols_persists(self, client: AsyncClient, db: Database):
        uid, token = await _register_and_get_token(client, "alice@test.com")
        resp = await client.put("/api/config/symbols", json={
            "stocks": ["MSFT", "GOOG"], "crypto": ["ETH/USD"],
        }, headers=_auth(token))
        assert resp.status_code == 200

        settings = await db.get_user_settings(uid)
        assert settings is not None
        import json
        config = json.loads(settings.symbols_config)
        assert config["stocks"] == ["MSFT", "GOOG"]
        assert config["crypto"] == ["ETH/USD"]
