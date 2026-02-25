"""CLI command to launch the Textual TUI dashboard."""

from __future__ import annotations

import typer

app = typer.Typer(help="Interactive TUI dashboard for monitoring the trade bot.")


@app.callback(invoke_without_command=True)
def launch(
    api_url: str = typer.Option(
        "http://localhost:8000",
        "--api-url",
        help="Dashboard API base URL",
    ),
    refresh: int = typer.Option(30, "--refresh", help="Auto-refresh interval in seconds"),
) -> None:
    """Launch the interactive TUI dashboard."""
    from src.cli.tui.app import DashboardApp

    DashboardApp(api_base=api_url, refresh_interval=refresh).run()
