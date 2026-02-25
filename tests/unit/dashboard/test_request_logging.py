"""Tests for request ID tracking middleware."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.dashboard.app import create_app
from src.dashboard.dependencies import require_user
from src.db.models import UserRecord


@pytest.fixture
def _test_user():
    return UserRecord(
        id="user-1",
        email="test@example.com",
        hashed_password="h",
        name="Test",
    )


@pytest.fixture
def client(_test_user):
    mock_db = AsyncMock()
    mock_db.get_user_settings.return_value = None
    app = create_app(db=mock_db)
    app.dependency_overrides[require_user] = lambda: _test_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestRequestIDMiddleware:
    def test_response_includes_request_id_header(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert "x-request-id" in {k.lower() for k in resp.headers}

    def test_request_id_is_unique_per_request(self, client):
        resp1 = client.get("/api/health")
        resp2 = client.get("/api/health")
        id1 = resp1.headers.get("X-Request-ID")
        id2 = resp2.headers.get("X-Request-ID")
        assert id1 != id2

    def test_client_provided_request_id_is_echoed(self, client):
        resp = client.get("/api/health", headers={"X-Request-ID": "my-req-123"})
        assert resp.headers.get("X-Request-ID") == "my-req-123"
