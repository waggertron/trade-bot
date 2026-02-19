"""Simulation panel for the TUI dashboard."""
from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Label, RichLog, Static
from textual import work

logger = logging.getLogger(__name__)


class SimulationPanel(Static):
    """Shows recent simulation runs and selected run details."""

    DEFAULT_CSS = """
    SimulationPanel {
        padding: 1 2;
    }
    SimulationPanel .section-title {
        text-style: bold;
        margin-bottom: 1;
    }
    SimulationPanel DataTable {
        height: auto;
        max-height: 12;
    }
    SimulationPanel RichLog {
        height: 15;
        margin-top: 1;
        border: solid $primary;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Simulation Runs", classes="section-title")
            table = DataTable(id="sim-runs")
            table.add_columns("ID", "Status", "Stocks", "Started")
            table.cursor_type = "row"
            yield table
            yield Label("")
            yield Label("Run Details", classes="section-title")
            yield RichLog(id="sim-details", highlight=True)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Show details when a simulation run row is selected."""
        log = self.query_one("#sim-details", RichLog)
        log.clear()
        row_data = event.data_table.get_row(event.row_key)
        if row_data:
            log.write(f"Run ID: {row_data[0]}")
            log.write(f"Status: {row_data[1]}")
            log.write(f"Stocks: {row_data[2]}")
            log.write(f"Started: {row_data[3]}")

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        """Fetch simulation runs from the API."""
        api = self.app.api_client  # type: ignore[attr-defined]

        try:
            runs = await api.get_simulation_runs()
            table = self.query_one("#sim-runs", DataTable)
            table.clear()
            for run in runs[:20]:  # Show last 20
                config = run.get("config", {})
                stocks = config.get("stocks", [])
                table.add_row(
                    str(run.get("id", "")),
                    str(run.get("status", "")),
                    f"{len(stocks)} stocks",
                    str(run.get("started_at", ""))[:19],
                )
        except Exception:
            logger.debug("Panel render error", exc_info=True)
