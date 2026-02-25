"""Risk panel for the TUI dashboard."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from textual import work
from textual.containers import Vertical
from textual.widgets import DataTable, Label, ProgressBar, Static

if TYPE_CHECKING:
    from textual.app import ComposeResult

logger = logging.getLogger(__name__)


class RiskPanel(Static):
    """Shows risk settings, drawdown progress, circuit breaker, and regime."""

    DEFAULT_CSS = """
    RiskPanel {
        padding: 1 2;
    }
    RiskPanel .section-title {
        text-style: bold;
        margin-bottom: 1;
    }
    RiskPanel ProgressBar {
        margin: 1 0;
    }
    RiskPanel DataTable {
        height: auto;
        max-height: 15;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Risk Management", classes="section-title")
            yield Label("Drawdown", classes="section-title")
            yield Label("Current: [dim]...[/dim]", id="risk-dd-label")
            yield ProgressBar(total=100, id="risk-dd-bar")
            yield Label("")
            yield Label("Circuit Breaker", classes="section-title")
            yield Label("Status: [dim]loading...[/dim]", id="risk-cb")
            yield Label("")
            yield Label("Volatility Regime", classes="section-title")
            yield Label("Regime: [dim]...[/dim]", id="risk-regime")
            yield Label("")
            yield Label("Risk Settings", classes="section-title")
            table = DataTable(id="risk-settings")
            table.add_columns("Setting", "Value")
            yield table

    def _update_label(self, selector: str, text: str) -> None:
        try:
            self.query_one(selector, Label).update(text)
        except Exception:
            logger.debug("Panel render error", exc_info=True)

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        """Fetch risk data from the API."""
        api = self.app.api_client  # type: ignore[attr-defined]

        try:
            dd = await api.get_drawdown()
            current = dd.get("current_drawdown_pct", 0)
            limit = dd.get("max_allowed_pct", 10)
            self._update_label(
                "#risk-dd-label",
                f"Current: {current:.2f}% / {limit:.1f}% limit",
            )
            try:
                bar = self.query_one("#risk-dd-bar", ProgressBar)
                bar.total = limit
                bar.progress = min(current, limit)
            except Exception:
                logger.debug("Panel render error", exc_info=True)
        except Exception:
            self._update_label("#risk-dd-label", "Current: [red]error[/red]")

        try:
            cb = await api.get_circuit_breaker()
            tripped = cb.get("tripped", False)
            color = "red" if tripped else "green"
            self._update_label(
                "#risk-cb",
                f"Status: [{color}]{'TRIPPED' if tripped else 'OK'}[/{color}]",
            )
        except Exception:
            logger.debug("Panel render error", exc_info=True)

        try:
            regime = await api.get_regime()
            regime_name = regime.get("regime", "unknown")
            self._update_label("#risk-regime", f"Regime: [bold]{regime_name}[/bold]")
        except Exception:
            logger.debug("Panel render error", exc_info=True)

        try:
            status = await api.get_risk_status()
            table = self.query_one("#risk-settings", DataTable)
            table.clear()
            for key, value in status.items():
                if key not in ("risk_level",):
                    table.add_row(str(key), str(value))
        except Exception:
            logger.debug("Panel render error", exc_info=True)
