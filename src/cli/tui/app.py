"""Textual TUI dashboard application."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

from src.cli.tui.api_client import DashboardAPIClient
from src.cli.tui.panels.portfolio import PortfolioPanel
from src.cli.tui.panels.risk import RiskPanel
from src.cli.tui.panels.simulation import SimulationPanel
from src.cli.tui.panels.system import SystemPanel


class DashboardApp(App):
    """Trade Bot TUI Dashboard."""

    CSS_PATH = "app.tcss"
    TITLE = "Trade Bot Dashboard"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh_all", "Refresh"),
    ]

    def __init__(
        self,
        api_base: str = "http://localhost:8000",
        refresh_interval: int = 30,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.api_client = DashboardAPIClient(base_url=api_base)
        self._refresh_interval = refresh_interval

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent():
            with TabPane("Portfolio", id="portfolio"):
                yield PortfolioPanel()
            with TabPane("Risk", id="risk"):
                yield RiskPanel()
            with TabPane("Simulations", id="simulations"):
                yield SimulationPanel()
            with TabPane("System", id="system"):
                yield SystemPanel()
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(self._refresh_interval, self.action_refresh_all)
        self.action_refresh_all()

    def action_refresh_all(self) -> None:
        """Refresh all panels."""
        for panel in self.query(PortfolioPanel):
            panel.refresh_data()
        for panel in self.query(RiskPanel):
            panel.refresh_data()
        for panel in self.query(SimulationPanel):
            panel.refresh_data()
        for panel in self.query(SystemPanel):
            panel.refresh_data()
