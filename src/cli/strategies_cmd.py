"""Strategy inspection CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from src.cli.charts import plotext_bar_chart

app = typer.Typer(name="strategies", help="Strategy inspection commands.", no_args_is_help=True)

console = Console()

# Registry of known strategies with their type and required features.
_STRATEGIES: list[dict[str, object]] = [
    {
        "name": "momentum",
        "type": "FeatureStrategy adapter",
        "features": ["sma_5", "sma_14"],
        "weight": 1.0,
    },
    {
        "name": "sentiment",
        "type": "FeatureStrategy adapter",
        "features": ["sentiment_avg_6h"],
        "weight": 0.8,
    },
    {
        "name": "quantitative",
        "type": "FeatureStrategy adapter",
        "features": ["price_zscore"],
        "weight": 1.2,
    },
    {
        "name": "ml_ensemble",
        "type": "ML-driven",
        "features": ["all engineered features"],
        "weight": 1.5,
    },
    {
        "name": "event_driven",
        "type": "event-based",
        "features": ["news_events", "earnings_calendar"],
        "weight": 0.6,
    },
    {
        "name": "cross_asset",
        "type": "cross-asset correlation",
        "features": ["cross_correlation_matrix"],
        "weight": 0.9,
    },
]

# Collect all unique features across strategies for the requirement matrix
_ALL_FEATURES: list[str] = sorted(
    {f for s in _STRATEGIES if isinstance(s["features"], list) for f in s["features"]}
)


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

    # Feature requirement matrix showing which strategy needs which feature
    try:
        console.print()
        req_table = Table(title="Feature Requirement Matrix")
        req_table.add_column("Feature", style="cyan")
        for strat in _STRATEGIES:
            req_table.add_column(str(strat["name"]), justify="center")

        for feature in _ALL_FEATURES:
            row = [feature]
            for strat in _STRATEGIES:
                feats = strat["features"]
                if isinstance(feats, list) and feature in feats:
                    row.append("[green]\u2713[/green]")
                else:
                    row.append("[dim]\u2500[/dim]")
            req_table.add_row(*row)

        console.print(req_table)
    except Exception:
        pass  # Don't crash the command if matrix rendering fails

    # Strategy weight comparison bar chart
    try:
        console.print()
        labels = [str(s["name"]) for s in _STRATEGIES]
        values = [float(s["weight"]) for s in _STRATEGIES]
        chart = plotext_bar_chart(labels, values, title="Strategy Weight Comparison")
        console.print(chart)
    except Exception:
        pass  # Don't crash the command if chart rendering fails


@app.command()
def status() -> None:
    """Show strategy module summary."""
    typer.echo("Strategy Module")
    typer.echo(f"  Number of strategies: {len(_STRATEGIES)}")
    types = sorted({str(s["type"]) for s in _STRATEGIES})
    typer.echo(f"  Strategy types available: {', '.join(types)}")
    typer.echo("  Consensus method: WeightedConsensus")
