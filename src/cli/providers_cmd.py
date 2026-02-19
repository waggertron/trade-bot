"""CLI commands for provider management."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.providers.protocols import (
    DataStore,
    FeatureProvider,
    MarketDataProvider,
    NewsProvider,
    OnChainProvider,
    SentimentAnalyzer,
)
from src.providers.registry import ProviderRegistry

app = typer.Typer(name="providers", help="Provider management commands.", no_args_is_help=True)
console = Console()

# Status indicator symbols
_HEALTHY = "[green]\u2705[/green]"  # green checkmark
_UNHEALTHY = "[red]\u274c[/red]"  # red X mark

# Known implementations catalog
# Maps protocol_name -> list of (name, type, description)
PROVIDER_CATALOG: dict[str, list[tuple[str, str, str]]] = {
    "market_data": [
        ("mock_market", "mock", "Mock market data provider for testing"),
        ("kraken", "external", "Kraken cryptocurrency exchange"),
        ("binance", "external", "Binance cryptocurrency exchange"),
    ],
    "news": [
        ("mock_news", "mock", "Mock news provider for testing"),
        ("rss", "local", "RSS feed aggregator"),
        ("newsapi", "external", "NewsAPI.org news service"),
    ],
    "sentiment": [
        ("mock_sentiment", "mock", "Mock sentiment analyzer for testing"),
        ("ollama", "local", "Ollama local LLM sentiment analysis"),
        ("claude", "external", "Claude AI sentiment analysis"),
    ],
    "onchain": [
        ("mock_onchain", "mock", "Mock on-chain metrics provider for testing"),
    ],
    "features": [
        ("mock_feature", "mock", "Mock feature provider for testing"),
    ],
    "data_store": [
        ("mock_datastore", "mock", "In-memory mock data store for testing"),
    ],
}

# Map protocol filter names to protocol classes
PROTOCOL_MAP: dict[str, type] = {
    "market_data": MarketDataProvider,
    "news": NewsProvider,
    "sentiment": SentimentAnalyzer,
    "onchain": OnChainProvider,
    "features": FeatureProvider,
    "data_store": DataStore,
}


@app.command(name="list")
def list_providers(
    protocol: Annotated[
        str | None,
        typer.Option("--protocol", help="Filter by protocol type."),
    ] = None,
) -> None:
    """List known provider implementations."""
    table = Table(title="Known Providers")
    table.add_column("Protocol", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Description")

    if protocol is not None:
        if protocol not in PROVIDER_CATALOG:
            console.print(
                f"[red]Error:[/red] Unknown protocol '{protocol}'. "
                f"Available: {', '.join(sorted(PROVIDER_CATALOG))}"
            )
            raise typer.Exit(code=1)
        protocols_to_show = {protocol: PROVIDER_CATALOG[protocol]}
    else:
        protocols_to_show = PROVIDER_CATALOG

    for proto_name, implementations in protocols_to_show.items():
        for name, impl_type, description in implementations:
            table.add_row(proto_name, name, impl_type, description)

    console.print(table)


@app.command()
def health(
    mock: Annotated[bool, typer.Option("--mock/--no-mock", help="Use mock providers.")] = True,
) -> None:
    """Check health of registered providers."""
    if not mock:
        console.print("[yellow]Only mock providers are currently available.[/yellow]")
        raise typer.Exit(code=1)

    registry = ProviderRegistry.for_testing()

    table = Table(title="Provider Health")
    table.add_column("Protocol", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Status")

    async def _check_all() -> list[tuple[str, str, bool]]:
        results: list[tuple[str, str, bool]] = []
        for proto_name, instance in registry.all():
            provider_name = getattr(instance, "name", proto_name)
            if hasattr(instance, "health_check"):
                try:
                    healthy = await instance.health_check()
                except Exception:
                    healthy = False
                results.append((proto_name, provider_name, healthy))
            else:
                # Providers without health_check (e.g. SentimentAnalyzer, FeatureProvider)
                results.append((proto_name, provider_name, True))
        return results

    results = asyncio.run(_check_all())

    healthy_count = 0
    total_count = len(results)
    all_healthy = True

    for proto_name, provider_name, healthy in results:
        if healthy:
            indicator = _HEALTHY
            status = f"{indicator} [green]healthy[/green]"
            healthy_count += 1
        else:
            indicator = _UNHEALTHY
            status = f"{indicator} [red]unhealthy[/red]"
            all_healthy = False
        table.add_row(proto_name, provider_name, status)

    console.print(table)

    # Health summary bar
    if total_count > 0:
        color = "green" if all_healthy else ("yellow" if healthy_count > 0 else "red")
        bar_filled = int((healthy_count / total_count) * 20)
        bar_empty = 20 - bar_filled
        bar = f"[{color}]{'█' * bar_filled}[/{color}][dim]{'░' * bar_empty}[/dim]"
        summary = f"  {bar}  [{color}]{healthy_count}/{total_count} healthy[/{color}]"
        console.print()
        console.print(Panel(summary, title="Health Summary", border_style=color))

    if not all_healthy:
        raise typer.Exit(code=1)
