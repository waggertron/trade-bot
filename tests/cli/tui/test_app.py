"""Tests for the TUI DashboardApp."""
from __future__ import annotations

import pytest

from src.cli.tui.app import DashboardApp
from src.cli.tui.panels.portfolio import PortfolioPanel
from src.cli.tui.panels.risk import RiskPanel
from src.cli.tui.panels.simulation import SimulationPanel
from src.cli.tui.panels.system import SystemPanel


@pytest.mark.asyncio
async def test_app_mounts_with_four_tabs():
    """DashboardApp should mount with Portfolio, Risk, Simulations, System tabs."""
    app = DashboardApp(api_base="http://localhost:9999", refresh_interval=9999)
    async with app.run_test(size=(120, 40)) as pilot:
        # Verify all four panels exist
        assert len(app.query(PortfolioPanel)) == 1
        assert len(app.query(RiskPanel)) == 1
        assert len(app.query(SimulationPanel)) == 1
        assert len(app.query(SystemPanel)) == 1


@pytest.mark.asyncio
async def test_app_has_header_and_footer():
    """DashboardApp should have a header and footer."""
    from textual.widgets import Footer, Header

    app = DashboardApp(api_base="http://localhost:9999", refresh_interval=9999)
    async with app.run_test(size=(120, 40)) as pilot:
        assert len(app.query(Header)) == 1
        assert len(app.query(Footer)) == 1


@pytest.mark.asyncio
async def test_app_title():
    """DashboardApp should have correct title."""
    app = DashboardApp(api_base="http://localhost:9999", refresh_interval=9999)
    async with app.run_test(size=(120, 40)) as pilot:
        assert app.title == "Trade Bot Dashboard"
