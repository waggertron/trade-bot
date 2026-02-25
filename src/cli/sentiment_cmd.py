"""Sentiment pipeline CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.cli.charts import ascii_line_chart
from src.core.config import Settings

app = typer.Typer(name="sentiment", help="Sentiment pipeline commands.", no_args_is_help=True)
console = Console()

# Unicode block characters for sentiment gauge
_GAUGE_FULL = "\u2588"
_GAUGE_EMPTY = "\u2591"


def _load_settings() -> Settings:
    """Load settings from config/settings.yaml, falling back to defaults."""
    path = Path("config/settings.yaml")
    if path.exists():
        return Settings.from_yaml(path)
    return Settings()


def _sentiment_gauge(score: float, width: int = 20) -> str:
    """Render a sentiment score gauge using Unicode blocks.

    Score range is -1.0 to 1.0.  The gauge center represents 0 (neutral).
    Positive scores fill rightward in green, negative fill leftward in red.
    """
    half = width // 2
    clamped = max(-1.0, min(1.0, score))
    if clamped >= 0:
        right_filled = int(clamped * half)
        left_bar = _GAUGE_EMPTY * half
        right_bar = _GAUGE_FULL * right_filled + _GAUGE_EMPTY * (half - right_filled)
        return f"[dim]{left_bar}[/dim][green]{right_bar}[/green] {score:+.2f}"
    else:
        left_filled = int(abs(clamped) * half)
        left_bar = _GAUGE_EMPTY * (half - left_filled) + _GAUGE_FULL * left_filled
        right_bar = _GAUGE_EMPTY * half
        return f"[red]{left_bar}[/red][dim]{right_bar}[/dim] {score:+.2f}"


@app.command()
def status() -> None:
    """Show sentiment pipeline configuration and status."""
    settings = _load_settings()
    cfg = settings.sentiment

    console.print("[bold]Sentiment Pipeline Status[/bold]")
    console.print()

    enabled_str = "[green]Yes[/green]" if cfg.enabled else "[red]No[/red]"
    console.print(f"  Enabled:    {enabled_str}")
    console.print(f"  Analyzer:   {cfg.analyzer}")
    console.print("  Feeds:      DB-managed (see 'feeds' table)")
    console.print(f"  Interval:   {cfg.pipeline_interval_seconds}s")

    console.print()
    console.print(
        "[dim]  Run 'tradebot sentiment scores --symbol <SYM>' to see per-symbol scores.[/dim]"
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

    # Sentiment score gauge
    try:
        console.print()
        console.print("[bold]Sentiment Gauge[/bold]")
        example_scores = {
            "overall": 0.0,
            "news": 0.0,
            "social": 0.0,
        }
        for analyzer, score in example_scores.items():
            console.print(f"  {analyzer:<12} {_sentiment_gauge(score)}")
    except Exception:
        pass

    # Sentiment timeline chart placeholder
    try:
        console.print()
        console.print("[bold]Sentiment Timeline[/bold]")
        console.print(
            "[dim]No historical sentiment data available. "
            "Run pipeline cycles to populate the timeline.[/dim]"
        )
        _ = ascii_line_chart  # Acknowledge import for future use
    except Exception:
        pass
