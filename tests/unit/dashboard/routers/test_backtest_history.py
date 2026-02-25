"""Tests that backtest runs are persisted to and retrieved from the database."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-backtest-history-tests!")

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
    user = UserRecord(email="backtest@example.com", hashed_password="h", name="Backtest")
    await db.create_user(user)
    token = create_access_token(user_id=user.id, secret=settings.auth.jwt_secret_key)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client(db, settings):
    app = create_app(db=db, settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestBacktestHistory:
    async def test_runs_empty_initially(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/backtest/runs", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_run_is_persisted_to_db(
        self, client: AsyncClient, auth_headers: dict, db: Database
    ):
        """A backtest run should be persisted to the database."""
        run_resp = await client.post(
            "/api/backtest/run",
            headers=auth_headers,
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "strategies": ["momentum"],
                "symbols": ["AAPL"],
                "initial_capital": 10000,
            },
        )
        assert run_resp.status_code == 200
        run_id = run_resp.json()["id"]

        # Verify it's in the DB directly
        db_run = await db.get_backtest_run(run_id)
        assert db_run is not None
        assert db_run["id"] == run_id

    async def test_runs_retrieved_from_db(
        self, client: AsyncClient, auth_headers: dict, db: Database
    ):
        """Runs list should come from DB, not just in-memory."""
        # Create a run via API
        await client.post(
            "/api/backtest/run",
            headers=auth_headers,
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "strategies": [],
                "symbols": [],
                "initial_capital": 50000,
            },
        )

        # Should appear in list (from DB)
        list_resp = await client.get("/api/backtest/runs", headers=auth_headers)
        assert list_resp.status_code == 200
        runs = list_resp.json()
        assert len(runs) >= 1

    async def test_run_retrievable_by_id(
        self, client: AsyncClient, auth_headers: dict
    ):
        run_resp = await client.post(
            "/api/backtest/run",
            headers=auth_headers,
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "strategies": [],
                "symbols": [],
                "initial_capital": 50000,
            },
        )
        run_id = run_resp.json()["id"]

        get_resp = await client.get(
            f"/api/backtest/runs/{run_id}", headers=auth_headers
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == run_id
