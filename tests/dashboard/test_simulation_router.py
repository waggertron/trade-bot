"""Tests for the simulation API router."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.dashboard.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_simulation_run_endpoint(client):
    mock_report = {
        "id": "test123",
        "status": "completed",
        "config": {"stocks": ["AAPL"], "initial_balance": 10000.0, "train_days": 60, "test_days": 30, "risk_levels": ["moderate"], "mc_simulations": 50},
        "risk_level_results": {},
        "recommendation": None,
        "started_at": "2026-01-01T00:00:00",
        "completed_at": "2026-01-01T00:01:00",
        "error": None,
    }

    with patch("src.dashboard.routers.simulation._run_async", new_callable=AsyncMock, return_value=mock_report):
        resp = client.post("/api/simulation/run", json={
            "stocks": ["AAPL"],
            "initial_balance": 10000.0,
            "train_days": 60,
            "test_days": 30,
            "risk_levels": ["moderate"],
            "mc_simulations": 50,
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "test123"
    assert data["status"] == "completed"


def test_simulation_list_runs(client):
    resp = client.get("/api/simulation/runs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_simulation_get_run_not_found(client):
    resp = client.get("/api/simulation/runs/nonexistent")
    assert resp.status_code == 404
