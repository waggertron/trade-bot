"""Tests that ML router returns state from actual model when available."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-ml-router-tests!!!!!!")

from src.auth.tokens import create_access_token
from src.dashboard import dependencies
from src.dashboard.app import create_app
from src.db.database import Database
from src.db.models import UserRecord
from src.ml.models import EvalMetrics, Prediction


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
    user = UserRecord(email="ml@example.com", hashed_password="h", name="ML")
    await db.create_user(user)
    token = create_access_token(user_id=user.id, secret=settings.auth.jwt_secret_key)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_model():
    model = AsyncMock()
    model.name = "test_lstm"
    model.predict = AsyncMock(
        return_value=Prediction(
            direction="buy",
            confidence=0.85,
            model="test_lstm",
        )
    )
    model.evaluate = AsyncMock(
        return_value=EvalMetrics(
            model="test_lstm",
            accuracy=0.72,
            precision=0.68,
            recall=0.75,
            sharpe=1.2,
            test_samples=100,
        )
    )
    return model


@pytest.fixture
async def client(db, settings, mock_model):
    dependencies.state.ml_model = mock_model
    app = create_app(db=db, settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestMLRouterLive:
    async def test_models_list_returns_model_info(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/ml/models", headers=auth_headers)
        assert resp.status_code == 200
        models = resp.json()
        assert len(models) >= 1
        assert models[0]["name"] == "test_lstm"

    async def test_models_empty_when_no_model(self, db, settings, auth_headers):
        """Without ml_model in state, returns empty list."""
        dependencies.state.ml_model = None
        app = create_app(db=db, settings=settings)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/ml/models", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_predictions_returns_data(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/ml/predictions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    async def test_train_triggers_training(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/ml/train", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "training_started"
