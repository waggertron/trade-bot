"""Tests for the enhanced health endpoint with DB connectivity check."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.dashboard.app import create_app


class TestHealthEndpoint:
    def test_health_returns_ok_with_db(self):
        mock_db = AsyncMock()
        mock_db.check_health.return_value = True
        mock_db.get_user_settings.return_value = None

        app = create_app(db=mock_db)
        with TestClient(app) as client:
            resp = client.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"

    def test_health_reports_db_disconnected(self):
        mock_db = AsyncMock()
        mock_db.check_health.side_effect = Exception("Connection refused")
        mock_db.get_user_settings.return_value = None

        app = create_app(db=mock_db)
        with TestClient(app) as client:
            resp = client.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"

    def test_health_works_without_db(self):
        app = create_app(db=None)
        with TestClient(app) as client:
            resp = client.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "not configured"
