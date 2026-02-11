"""ML pipeline CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="ml", help="ML pipeline commands.", no_args_is_help=True
)
console = Console()


@app.command()
def status() -> None:
    """Show ML pipeline status summary."""
    console.print("[bold]ML Pipeline Status[/bold]")
    console.print("  Feature Store: (empty)")
    console.print("  Models: (none loaded)")
    console.print(
        "  Use 'tradebot ml features --symbol <SYM>' to see stored features."
    )


@app.command()
def features(
    symbol: str = typer.Option(..., help="Symbol to show features for"),
) -> None:
    """Show stored features for a symbol."""
    table = Table(title=f"Features: {symbol}")
    table.add_column("Feature")
    table.add_column("Value")
    table.add_column("Timestamp")
    console.print(table)
    console.print("No features stored yet. Run a feature computation cycle first.")
