"""Tests for the Risk panel."""
from __future__ import annotations

import pytest

from src.cli.tui.app import DashboardApp
from src.cli.tui.panels.risk import RiskPanel


@pytest.mark.asyncio
async def test_risk_panel_mounts():
    """RiskPanel should mount with expected widgets."""
    app = DashboardApp(api_base="http://localhost:9999", refresh_interval=9999)
    async with app.run_test(size=(120, 40)) as pilot:
        panels = app.query(RiskPanel)
        assert len(panels) == 1
        assert app.query_one("#risk-dd-bar") is not None
        assert app.query_one("#risk-cb") is not None
        assert app.query_one("#risk-regime") is not None
