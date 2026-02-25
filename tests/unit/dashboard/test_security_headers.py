"""Tests for security headers middleware."""

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


class TestSecurityHeaders:
    def test_x_content_type_options(self, client):
        resp = client.get("/api/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, client):
        resp = client.get("/api/health")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_strict_transport_security(self, client):
        resp = client.get("/api/health")
        hsts = resp.headers.get("Strict-Transport-Security")
        assert hsts is not None
        assert "max-age=" in hsts

    def test_referrer_policy(self, client):
        resp = client.get("/api/health")
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_headers_present_on_authenticated_endpoints(self, client):
        resp = client.get("/api/trades")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
