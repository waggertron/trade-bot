"""System status panel for the TUI dashboard."""
from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Label, Static
from textual import work

logger = logging.getLogger(__name__)


class SystemPanel(Static):
    """Shows API health, trade mode, strategy count, and uptime."""

    DEFAULT_CSS = """
    SystemPanel {
        padding: 1 2;
    }
    SystemPanel .section-title {
        text-style: bold;
        margin-bottom: 1;
    }
    SystemPanel .status-row {
        margin-bottom: 0;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("System Status", classes="section-title")
            yield Label("API: [dim]checking...[/dim]", id="sys-health")
            yield Label("Mode: [dim]...[/dim]", id="sys-mode")
            yield Label("Strategies: [dim]...[/dim]", id="sys-strategies")
            yield Label("Uptime: [dim]...[/dim]", id="sys-uptime")
            yield Label("Paused: [dim]...[/dim]", id="sys-paused")

    def _update_label(self, selector: str, text: str) -> None:
        """Safely update a label, ignoring NoMatches."""
        try:
            self.query_one(selector, Label).update(text)
        except Exception:
            logger.debug("Panel render error", exc_info=True)

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        """Fetch system status from the API."""
        api = self.app.api_client  # type: ignore[attr-defined]
        try:
            health = await api.get_health()
            status_text = health.get("status", "unknown")
            self._update_label("#sys-health", f"API: [green]{status_text}[/green]")
        except Exception:
            self._update_label("#sys-health", "API: [red]unreachable[/red]")

        try:
            sys_info = await api.get_system_status()
            self._update_label(
                "#sys-mode", f"Mode: [bold]{sys_info.get('mode', '?')}[/bold]",
            )
            self._update_label(
                "#sys-strategies", f"Strategies: {sys_info.get('strategies_count', 0)}",
            )
            uptime_s = sys_info.get("uptime_seconds", 0)
            h, rem = divmod(uptime_s, 3600)
            m, s = divmod(rem, 60)
            self._update_label("#sys-uptime", f"Uptime: {h}h {m}m {s}s")
            paused = sys_info.get("is_paused", False)
            color = "red" if paused else "green"
            self._update_label(
                "#sys-paused", f"Paused: [{color}]{paused}[/{color}]",
            )
        except Exception:
            logger.debug("Panel render error", exc_info=True)
