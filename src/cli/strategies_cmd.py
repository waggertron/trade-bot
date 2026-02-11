"""Strategy inspection CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="strategies", help="Strategy inspection commands.", no_args_is_help=True
)

console = Console()

# Registry of known strategies with their type and required features.
_STRATEGIES: list[dict[str, object]] = [
    {
        "name": "momentum",
        "type": "FeatureStrategy adapter",
        "features": ["sma_5", "sma_14"],
    },
    {
        "name": "sentiment",
        "type": "FeatureStrategy adapter",
        "features": ["sentiment_avg_6h"],
    },
    {
        "name": "quantitative",
        "type": "FeatureStrategy adapter",
        "features": ["price_zscore"],
    },
    {
        "name": "ml_ensemble",
        "type": "ML-driven",
        "features": ["all engineered features"],
    },
    {
        "name": "event_driven",
        "type": "event-based",
        "features": ["news_events", "earnings_calendar"],
    },
    {
        "name": "cross_asset",
        "type": "cross-asset correlation",
        "features": ["cross_correlation_matrix"],
    },
]


@app.command("list")
def list_strategies() -> None:
    """List all registered strategies with their type and required features."""
    table = Table(title="Registered Strategies")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Required Features", style="yellow")

    for strat in _STRATEGIES:
        features = strat["features"]
        features_str = ", ".join(features) if isinstance(features, list) else str(features)
        table.add_row(
            str(strat["name"]),
            str(strat["type"]),
            features_str,
        )

    console.print(table)


@app.command()
def status() -> None:
    """Show strategy module summary."""
    typer.echo("Strategy Module")
    typer.echo(f"  Number of strategies: {len(_STRATEGIES)}")
    types = sorted({str(s["type"]) for s in _STRATEGIES})
    typer.echo(f"  Strategy types available: {', '.join(types)}")
    typer.echo("  Consensus method: WeightedConsensus")
