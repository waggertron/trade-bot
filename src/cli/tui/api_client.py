"""Async API client for the trade bot dashboard."""

from __future__ import annotations

import httpx


class DashboardAPIClient:
    """Thin async httpx wrapper for dashboard API endpoints."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str) -> dict | list:
        resp = await self._client.get(path)
        resp.raise_for_status()
        return resp.json()

    # -- Health / System --
    async def get_health(self) -> dict:
        return await self._get("/api/health")

    async def get_system_status(self) -> dict:
        return await self._get("/api/system/status")

    # -- Portfolio --
    async def get_portfolio(self) -> dict:
        return await self._get("/api/portfolio")

    async def get_positions(self) -> list:
        return await self._get("/api/portfolio/positions")

    async def get_pnl(self) -> dict:
        return await self._get("/api/portfolio/pnl")

    async def get_equity_curve(self) -> dict:
        return await self._get("/api/portfolio/equity-curve")

    # -- Risk --
    async def get_risk_status(self) -> dict:
        return await self._get("/api/risk/status")

    async def get_drawdown(self) -> dict:
        return await self._get("/api/risk/drawdown")

    async def get_circuit_breaker(self) -> dict:
        return await self._get("/api/risk/circuit-breaker")

    async def get_regime(self) -> dict:
        return await self._get("/api/risk/regime")

    # -- Simulation --
    async def get_simulation_runs(self) -> list:
        return await self._get("/api/simulation/runs")

    # -- Config --
    async def get_config(self) -> dict:
        return await self._get("/api/config")
