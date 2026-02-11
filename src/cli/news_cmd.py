"""News CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="news", help="News operations commands.", no_args_is_help=True
)

console = Console()

_PROVIDERS = [
    {"name": "RSS", "description": "RSS feed aggregator", "status": "Available"},
    {"name": "Reddit", "description": "Reddit sentiment scraper", "status": "Available"},
    {"name": "NewsAPI", "description": "NewsAPI.org provider", "status": "Available"},
    {"name": "Mock", "description": "Mock data for testing", "status": "Available"},
]

_EXAMPLE_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss.xml",
]


@app.command()
def status() -> None:
    """Show news module summary."""
    console.print()
    console.print("[bold]News Module Status[/bold]")
    console.print()

    table = Table(title="Available Providers")
    table.add_column("Provider", style="cyan")
    table.add_column("Description")
    table.add_column("Status", justify="center")

    for provider in _PROVIDERS:
        table.add_row(
            provider["name"],
            provider["description"],
            f"[green]{provider['status']}[/green]",
        )

    console.print(table)


@app.command()
def feeds() -> None:
    """Show configured RSS feed URLs."""
    console.print()
    console.print("[bold]Configured RSS Feeds[/bold]")
    console.print()

    table = Table(title="RSS Feeds")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Feed URL", style="cyan")

    for idx, url in enumerate(_EXAMPLE_FEEDS, start=1):
        table.add_row(str(idx), url)

    console.print(table)
