"""Analytics CLI commands."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="analytics", help="Analytics commands.", no_args_is_help=True
)


@app.command()
def status() -> None:
    """Show analytics module summary."""
    typer.echo("Analytics Module")
    typer.echo("  Available analyzers:")
    typer.echo("    - StrategyAttribution")
    typer.echo("    - MonteCarloSimulator")
    typer.echo("    - RegimeTagger")
    typer.echo("    - AnalyticsReporter")
    typer.echo("  Status: Ready")


@app.command()
def attribution() -> None:
    """Show example attribution format."""
    typer.echo("Strategy Attribution")
    typer.echo(
        "No live trading data available. "
        "Run a backtest to generate attribution data."
    )
    typer.echo(
        "Available strategies: momentum, sentiment, "
        "quantitative, ml_ensemble, event_driven, cross_asset"
    )
