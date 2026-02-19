"""Tests for the System panel."""
from __future__ import annotations

import pytest

from src.cli.tui.app import DashboardApp
from src.cli.tui.panels.system import SystemPanel


@pytest.mark.asyncio
async def test_system_panel_mounts():
    """SystemPanel should mount with expected labels."""
    app = DashboardApp(api_base="http://localhost:9999", refresh_interval=9999)
    async with app.run_test(size=(120, 40)) as pilot:
        panels = app.query(SystemPanel)
        assert len(panels) == 1
        # Verify key labels exist
        assert app.query_one("#sys-health") is not None
        assert app.query_one("#sys-mode") is not None
        assert app.query_one("#sys-strategies") is not None
