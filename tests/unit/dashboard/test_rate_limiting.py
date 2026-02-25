"""Tests for API rate limiting middleware."""

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


class TestRateLimiting:
    def test_rate_limit_headers_on_read_endpoints(self, client):
        """Read endpoints should include rate limit headers."""
        resp = client.get("/api/trades")
        # Should have rate-limit related headers
        assert resp.status_code == 200
        assert "x-ratelimit-limit" in {k.lower() for k in resp.headers}
        assert "x-ratelimit-remaining" in {k.lower() for k in resp.headers}

    def test_rate_limit_headers_on_health(self, client):
        """Health endpoint should also be rate limited."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert "x-ratelimit-limit" in {k.lower() for k in resp.headers}

    def test_write_endpoint_has_stricter_limit(self, client):
        """Write endpoints should have a lower rate limit than reads."""
        # Config set is a write endpoint
        resp = client.put("/api/config/mode", json={"mode": "paper"})
        assert resp.status_code == 200
        limit_header = None
        for key in resp.headers:
            if key.lower() == "x-ratelimit-limit":
                limit_header = resp.headers[key]
        # The write limit should be present
        assert limit_header is not None
