"""News CLI commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.charts import plotext_bar_chart

app = typer.Typer(name="news", help="News operations commands.", no_args_is_help=True)

console = Console()

_PROVIDERS = [
    {
        "name": "RSS",
        "description": "RSS feed aggregator",
        "status": "Available",
        "article_count": 42,
    },
    {
        "name": "Reddit",
        "description": "Reddit sentiment scraper",
        "status": "Available",
        "article_count": 18,
    },
    {
        "name": "NewsAPI",
        "description": "NewsAPI.org provider",
        "status": "Available",
        "article_count": 65,
    },
    {
        "name": "Mock",
        "description": "Mock data for testing",
        "status": "Available",
        "article_count": 10,
    },
]

_EXAMPLE_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss.xml",
]

# Simulated last-fetch timestamps for feed freshness display
_FEED_FRESHNESS: dict[str, datetime] = {
    "https://feeds.finance.yahoo.com/rss/2.0/headline": datetime.now(UTC) - timedelta(minutes=5),
    "https://www.coindesk.com/arc/outboundfeeds/rss/": datetime.now(UTC) - timedelta(minutes=12),
    "https://cointelegraph.com/rss": datetime.now(UTC) - timedelta(minutes=30),
    "https://decrypt.co/feed": datetime.now(UTC) - timedelta(hours=2),
    "https://www.theblock.co/rss.xml": datetime.now(UTC) - timedelta(hours=6),
}


def _freshness_label(last_fetch: datetime) -> str:
    """Return a colored freshness label based on how recently a feed was fetched."""
    age = datetime.now(UTC) - last_fetch
    minutes = age.total_seconds() / 60
    if minutes < 15:
        return "[green]Fresh[/green] (<15m)"
    if minutes < 60:
        return f"[yellow]Aging[/yellow] ({int(minutes)}m ago)"
    hours = minutes / 60
    return f"[red]Stale[/red] ({hours:.1f}h ago)"


@app.command()
def status() -> None:
    """Show news module summary."""
    console.print()
    console.print("[bold]News Module Status[/bold]")
    console.print()

    table = Table(title="Available Providers")
    table.add_column("Provider", style="cyan")
    table.add_column("Description")
    table.add_column("Articles", justify="right", style="magenta")
    table.add_column("Status", justify="center")

    for provider in _PROVIDERS:
        table.add_row(
            provider["name"],
            provider["description"],
            str(provider["article_count"]),
            f"[green]{provider['status']}[/green]",
        )

    console.print(table)

    # Article count bar chart per provider
    try:
        labels = [p["name"] for p in _PROVIDERS]
        values = [p["article_count"] for p in _PROVIDERS]
        chart = plotext_bar_chart(labels, values, title="Articles per Provider")
        console.print()
        console.print(Panel(chart, title="Article Distribution", border_style="cyan"))
    except Exception:
        pass  # Gracefully skip chart if plotext fails


@app.command()
def feeds() -> None:
    """Show configured RSS feed URLs."""
    console.print()
    console.print("[bold]Configured RSS Feeds[/bold]")
    console.print()

    table = Table(title="RSS Feeds")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Feed URL", style="cyan")
    table.add_column("Freshness", justify="center")

    for idx, url in enumerate(_EXAMPLE_FEEDS, start=1):
        freshness = _FEED_FRESHNESS.get(url)
        label = _freshness_label(freshness) if freshness else "[dim]Unknown[/dim]"
        table.add_row(str(idx), url, label)

    console.print(table)
