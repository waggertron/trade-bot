"""Tests that strategy weight/enabled changes persist to the database."""

from __future__ import annotations

import json
import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-strategies-crud-tests!")

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
    s.ml_model = None


class FakeStrategy:
    """Minimal strategy object for testing."""

    def __init__(self, name: str, weight: float = 1.0, enabled: bool = True):
        self.name = name
        self.weight = weight
        self.enabled = enabled
        self.description = f"{name} strategy"


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
async def test_user(db: Database):
    user = UserRecord(email="strat@example.com", hashed_password="h", name="Strat")
    await db.create_user(user)
    return user


@pytest.fixture
async def auth_headers(test_user: UserRecord, settings):
    token = create_access_token(user_id=test_user.id, secret=settings.auth.jwt_secret_key)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fake_strategies():
    return [
        FakeStrategy("momentum", weight=1.0, enabled=True),
        FakeStrategy("mean_reversion", weight=0.5, enabled=False),
    ]


@pytest.fixture
async def client(db, settings, fake_strategies):
    app = create_app(db=db, settings=settings, strategy_list=fake_strategies)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestStrategiesCRUD:
    async def test_update_weight_persisted_to_db(
        self, client: AsyncClient, auth_headers: dict, db: Database, test_user: UserRecord
    ):
        """Updating a strategy weight should persist to user_settings in the DB."""
        resp = await client.put(
            "/api/strategies/momentum/weight",
            headers=auth_headers,
            json={"weight": 0.75},
        )
        assert resp.status_code == 200
        assert resp.json()["weight"] == 0.75

        # Verify it's persisted in DB
        settings_rec = await db.get_user_settings(test_user.id)
        assert settings_rec is not None
        weights = json.loads(settings_rec.strategy_weights)
        assert weights["momentum"]["weight"] == 0.75

    async def test_update_enabled_persisted_to_db(
        self, client: AsyncClient, auth_headers: dict, db: Database, test_user: UserRecord
    ):
        """Toggling strategy enabled should persist to user_settings in the DB."""
        resp = await client.put(
            "/api/strategies/mean_reversion/enabled",
            headers=auth_headers,
            json={"enabled": True},
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True

        # Verify it's persisted in DB
        settings_rec = await db.get_user_settings(test_user.id)
        assert settings_rec is not None
        weights = json.loads(settings_rec.strategy_weights)
        assert weights["mean_reversion"]["enabled"] is True

    async def test_list_strategies_reflects_persisted_changes(
        self, client: AsyncClient, auth_headers: dict
    ):
        """After updating weight, list should reflect the change."""
        await client.put(
            "/api/strategies/momentum/weight",
            headers=auth_headers,
            json={"weight": 0.3},
        )

        resp = await client.get("/api/strategies/", headers=auth_headers)
        assert resp.status_code == 200
        strategies = resp.json()
        momentum = next(s for s in strategies if s["name"] == "momentum")
        assert momentum["weight"] == 0.3

    async def test_weight_persists_across_requests(
        self, client: AsyncClient, auth_headers: dict, db: Database, test_user: UserRecord
    ):
        """Multiple updates should all persist correctly."""
        await client.put(
            "/api/strategies/momentum/weight",
            headers=auth_headers,
            json={"weight": 0.8},
        )
        await client.put(
            "/api/strategies/mean_reversion/enabled",
            headers=auth_headers,
            json={"enabled": True},
        )

        settings_rec = await db.get_user_settings(test_user.id)
        assert settings_rec is not None
        weights = json.loads(settings_rec.strategy_weights)
        assert weights["momentum"]["weight"] == 0.8
        assert weights["mean_reversion"]["enabled"] is True
