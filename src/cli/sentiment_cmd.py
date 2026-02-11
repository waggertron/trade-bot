"""Sentiment pipeline CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="sentiment", help="Sentiment pipeline commands.", no_args_is_help=True
)
console = Console()


@app.command()
def status() -> None:
    """Show sentiment pipeline status summary."""
    console.print("[bold]Sentiment Pipeline Status[/bold]")
    console.print("  Providers: (none active)")
    console.print("  Articles: 0")
    console.print("  Scores: 0")
    console.print(
        "  Use 'tradebot sentiment scores --symbol <SYM>' to see per-symbol scores."
    )


@app.command()
def scores(
    symbol: str = typer.Option(..., help="Symbol to show scores for"),
) -> None:
    """Show sentiment scores for a symbol."""
    table = Table(title=f"Sentiment Scores: {symbol}")
    table.add_column("Analyzer")
    table.add_column("Score")
    table.add_column("Magnitude")
    table.add_column("Time")
    console.print(table)
    console.print("No scores yet. Run a pipeline cycle first.")
