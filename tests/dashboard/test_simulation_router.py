"""Tests for the simulation API router."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.dashboard.app import create_app
from src.dashboard.dependencies import require_user
from src.db.models import UserRecord

_test_user = UserRecord(email="test@example.com", hashed_password="h", name="Test", is_verified=True)


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[require_user] = lambda: _test_user
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


def test_simulation_run_forwards_mc_seed(client):
    """mc_seed from request body is forwarded to SimulationConfig."""
    mock_report = {
        "id": "seed-test",
        "status": "completed",
        "config": {
            "stocks": ["AAPL"],
            "initial_balance": 10000.0,
            "train_days": 60,
            "test_days": 30,
            "risk_levels": ["moderate"],
            "mc_simulations": 50,
            "mc_seed": 42,
        },
        "risk_level_results": {},
        "recommendation": None,
        "started_at": "2026-01-01T00:00:00",
        "completed_at": "2026-01-01T00:01:00",
        "error": None,
    }

    with patch(
        "src.dashboard.routers.simulation._run_async",
        new_callable=AsyncMock,
        return_value=mock_report,
    ) as mock_run:
        resp = client.post("/api/simulation/run", json={
            "stocks": ["AAPL"],
            "initial_balance": 10000.0,
            "train_days": 60,
            "test_days": 30,
            "risk_levels": ["moderate"],
            "mc_simulations": 50,
            "mc_seed": 42,
        })

    assert resp.status_code == 200
    # Verify the request object passed to _run_async had mc_seed set
    call_args = mock_run.call_args
    req_arg = call_args[0][0]
    assert req_arg.mc_seed == 42


def test_simulation_run_forwards_max_position_pct(client):
    """max_position_pct from request body is forwarded to SimulationConfig."""
    mock_report = {
        "id": "pos-test",
        "status": "completed",
        "config": {
            "stocks": ["AAPL"],
            "initial_balance": 10000.0,
            "train_days": 60,
            "test_days": 30,
            "risk_levels": ["moderate"],
            "mc_simulations": 50,
            "max_position_pct": 5.0,
        },
        "risk_level_results": {},
        "recommendation": None,
        "started_at": "2026-01-01T00:00:00",
        "completed_at": "2026-01-01T00:01:00",
        "error": None,
    }

    with patch(
        "src.dashboard.routers.simulation._run_async",
        new_callable=AsyncMock,
        return_value=mock_report,
    ) as mock_run:
        resp = client.post("/api/simulation/run", json={
            "stocks": ["AAPL"],
            "initial_balance": 10000.0,
            "train_days": 60,
            "test_days": 30,
            "risk_levels": ["moderate"],
            "mc_simulations": 50,
            "max_position_pct": 5.0,
        })

    assert resp.status_code == 200
    call_args = mock_run.call_args
    req_arg = call_args[0][0]
    assert req_arg.max_position_pct == 5.0
