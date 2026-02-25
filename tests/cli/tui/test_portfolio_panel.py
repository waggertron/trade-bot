"""Tests for the Portfolio panel."""

from __future__ import annotations

import pytest

from src.cli.tui.app import DashboardApp
from src.cli.tui.panels.portfolio import PortfolioPanel


@pytest.mark.asyncio
async def test_portfolio_panel_mounts():
    """PortfolioPanel should mount with expected widgets."""
    app = DashboardApp(api_base="http://localhost:9999", refresh_interval=9999)
    async with app.run_test(size=(120, 40)):
        panels = app.query(PortfolioPanel)
        assert len(panels) == 1
        assert app.query_one("#pf-total") is not None
        assert app.query_one("#pf-positions") is not None
        assert app.query_one("#pf-sparkline") is not None
