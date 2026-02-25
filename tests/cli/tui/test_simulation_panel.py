"""Tests for the Simulation panel."""

from __future__ import annotations

import pytest

from src.cli.tui.app import DashboardApp
from src.cli.tui.panels.simulation import SimulationPanel


@pytest.mark.asyncio
async def test_simulation_panel_mounts():
    """SimulationPanel should mount with expected widgets."""
    app = DashboardApp(api_base="http://localhost:9999", refresh_interval=9999)
    async with app.run_test(size=(120, 40)):
        panels = app.query(SimulationPanel)
        assert len(panels) == 1
        assert app.query_one("#sim-runs") is not None
        assert app.query_one("#sim-details") is not None
