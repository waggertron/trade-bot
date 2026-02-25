"""Tests that request logging middleware logs method, path, status, duration."""

from __future__ import annotations

import logging
import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-request-logging-tests!")

from src.auth.tokens import create_access_token
from src.dashboard import dependencies
from src.dashboard.app import create_app
from src.db.database import Database
from src.db.models import UserRecord


@pytest.fixture(autouse=True)
def reset_state():
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
    yield
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
    user = UserRecord(email="log@example.com", hashed_password="h", name="Log")
    await db.create_user(user)
    token = create_access_token(user_id=user.id, secret=settings.auth.jwt_secret_key)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client(db, settings):
    app = create_app(db=db, settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestRequestLoggingMiddleware:
    async def test_logs_method_and_path(
        self, client: AsyncClient, auth_headers: dict, caplog
    ):
        """Each request should produce a log entry with method and path."""
        with caplog.at_level(logging.INFO, logger="src.dashboard.request_logging"):
            await client.get("/api/strategies/", headers=auth_headers)

        assert any(
            "GET" in r.message and "/api/strategies/" in r.message for r in caplog.records
        ), f"Expected log with 'GET /api/strategies/', got: {[r.message for r in caplog.records]}"

    async def test_logs_status_code(
        self, client: AsyncClient, auth_headers: dict, caplog
    ):
        """Log entry should include the response status code."""
        with caplog.at_level(logging.INFO, logger="src.dashboard.request_logging"):
            await client.get("/api/strategies/", headers=auth_headers)

        assert any(
            "200" in r.message for r in caplog.records
        ), f"Expected log with status 200, got: {[r.message for r in caplog.records]}"

    async def test_logs_duration(
        self, client: AsyncClient, auth_headers: dict, caplog
    ):
        """Log entry should include response duration in milliseconds."""
        with caplog.at_level(logging.INFO, logger="src.dashboard.request_logging"):
            await client.get("/api/strategies/", headers=auth_headers)

        assert any(
            "ms" in r.message for r in caplog.records
        ), f"Expected log with duration (ms), got: {[r.message for r in caplog.records]}"

    async def test_logs_4xx_as_warning(self, client: AsyncClient, caplog):
        """4xx responses should log at WARNING level."""
        with caplog.at_level(logging.WARNING, logger="src.dashboard.request_logging"):
            await client.get("/api/strategies/")  # No auth → 401

        warning_records = [
            r
            for r in caplog.records
            if r.levelno >= logging.WARNING and "401" in r.message
        ]
        assert len(warning_records) >= 1, (
            f"Expected WARNING log with 401, got: {[r.message for r in caplog.records]}"
        )
