"""Analytics CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console

from src.cli.charts import plotext_bar_chart

app = typer.Typer(name="analytics", help="Analytics commands.", no_args_is_help=True)
console = Console()

# Example attribution data used when no live data is available.
# This illustrates the format that real backtest results would populate.
_EXAMPLE_ATTRIBUTION: dict[str, dict[str, float]] = {
    "momentum": {"pnl": 1250.00, "contribution_pct": 32.0},
    "sentiment": {"pnl": 780.50, "contribution_pct": 20.0},
    "quantitative": {"pnl": 950.25, "contribution_pct": 24.3},
    "ml_ensemble": {"pnl": 620.00, "contribution_pct": 15.9},
    "event_driven": {"pnl": -180.75, "contribution_pct": -4.6},
    "cross_asset": {"pnl": 485.00, "contribution_pct": 12.4},
}


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
    typer.echo("No live trading data available. Run a backtest to generate attribution data.")
    typer.echo(
        "Available strategies: momentum, sentiment, "
        "quantitative, ml_ensemble, event_driven, cross_asset"
    )

    # Strategy P&L bar chart using example attribution data
    try:
        console.print()
        console.print("[bold]Example Attribution (sample data)[/bold]")
        labels = list(_EXAMPLE_ATTRIBUTION.keys())
        pnl_values = [v["pnl"] for v in _EXAMPLE_ATTRIBUTION.values()]
        chart = plotext_bar_chart(labels, pnl_values, title="Strategy P&L ($)")
        console.print(chart)
    except Exception:
        pass  # Don't crash the command if chart rendering fails

    # Contribution horizontal bars using Unicode blocks
    try:
        console.print()
        console.print("[bold]Contribution Breakdown[/bold]")
        max_abs = max(abs(v["contribution_pct"]) for v in _EXAMPLE_ATTRIBUTION.values())
        bar_width = 30
        for name, data in _EXAMPLE_ATTRIBUTION.items():
            pct = data["contribution_pct"]
            filled = int(abs(pct) / max_abs * bar_width) if max_abs > 0 else 0
            empty = bar_width - filled
            color = "green" if pct >= 0 else "red"
            bar = "\u2588" * filled + "\u2591" * empty
            console.print(f"  {name:<15} [{color}]{bar}[/{color}] {pct:+.1f}%")
    except Exception:
        pass  # Don't crash the command if contribution rendering fails
