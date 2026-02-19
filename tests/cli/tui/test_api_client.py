"""Tests for the TUI API client."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.cli.tui.api_client import DashboardAPIClient


@pytest.fixture
def client():
    return DashboardAPIClient(base_url="http://localhost:8000")


@pytest.mark.asyncio
async def test_get_health(client):
    with patch.object(client, "_get", new_callable=AsyncMock, return_value={"status": "ok"}) as mock:
        result = await client.get_health()
    mock.assert_called_once_with("/api/health")
    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_get_portfolio(client):
    with patch.object(
        client, "_get", new_callable=AsyncMock, return_value={"total_value": 50000},
    ) as mock:
        result = await client.get_portfolio()
    mock.assert_called_once_with("/api/portfolio")
    assert result["total_value"] == 50000


@pytest.mark.asyncio
async def test_get_positions(client):
    with patch.object(
        client, "_get", new_callable=AsyncMock,
        return_value=[{"symbol": "AAPL", "qty": 10}],
    ) as mock:
        result = await client.get_positions()
    mock.assert_called_once_with("/api/portfolio/positions")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_risk_status(client):
    with patch.object(
        client, "_get", new_callable=AsyncMock,
        return_value={"risk_level": "moderate"},
    ) as mock:
        result = await client.get_risk_status()
    mock.assert_called_once_with("/api/risk/status")
    assert result["risk_level"] == "moderate"


@pytest.mark.asyncio
async def test_get_system_status(client):
    with patch.object(
        client, "_get", new_callable=AsyncMock,
        return_value={"mode": "paper", "is_paused": False},
    ) as mock:
        result = await client.get_system_status()
    mock.assert_called_once_with("/api/system/status")
    assert result["mode"] == "paper"


@pytest.mark.asyncio
async def test_get_simulation_runs(client):
    with patch.object(
        client, "_get", new_callable=AsyncMock,
        return_value=[{"id": "abc123"}],
    ) as mock:
        result = await client.get_simulation_runs()
    mock.assert_called_once_with("/api/simulation/runs")
    assert result[0]["id"] == "abc123"


@pytest.mark.asyncio
async def test_get_drawdown(client):
    with patch.object(
        client, "_get", new_callable=AsyncMock,
        return_value={"current": 2.5},
    ) as mock:
        result = await client.get_drawdown()
    mock.assert_called_once_with("/api/risk/drawdown")
    assert result["current"] == 2.5


@pytest.mark.asyncio
async def test_get_config(client):
    with patch.object(
        client, "_get", new_callable=AsyncMock,
        return_value={"mode": "paper"},
    ) as mock:
        result = await client.get_config()
    mock.assert_called_once_with("/api/config")
    assert result["mode"] == "paper"


@pytest.mark.asyncio
async def test_error_handling(client):
    """API errors should propagate as exceptions."""
    import httpx

    with patch.object(
        client, "_get", new_callable=AsyncMock,
        side_effect=httpx.HTTPStatusError(
            "500", request=AsyncMock(), response=AsyncMock(),
        ),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_health()
