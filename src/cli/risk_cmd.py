"""Risk management CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.rule import Rule

from src.agents.risk_manager import REGIME_LIMITS
from src.cli.charts import plotext_bar_chart
from src.core.config import RiskSettings
from src.risk.models import VolatilityRegime

app = typer.Typer(name="risk", help="Risk management commands.", no_args_is_help=True)
console = Console()

# Unicode block characters for visual gauges (ascending fill)
_GAUGE_CHARS = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"


def _risk_gauge(value: float, max_value: float, width: int = 20) -> str:
    """Render a visual risk gauge using Unicode blocks.

    Parameters
    ----------
    value : float
        The current value to display.
    max_value : float
        The maximum expected value (used for scaling).
    width : int
        Width of the gauge bar in characters.

    Returns
    -------
    str
        A string like ``[green]████████░░░░░░░░░░░░[/green] 40%``.
    """
    if max_value <= 0:
        return "[dim]N/A[/dim]"
    ratio = min(value / max_value, 1.0)
    filled = int(ratio * width)
    empty = width - filled
    # Color based on how "full" the gauge is
    if ratio < 0.4:
        color = "green"
    elif ratio < 0.7:
        color = "yellow"
    else:
        color = "red"
    bar = "\u2588" * filled + "\u2591" * empty
    return f"[{color}]{bar}[/{color}] {value:.1f}"


@app.command()
def status() -> None:
    """Show current risk settings summary."""
    settings = RiskSettings()
    typer.echo("Risk Settings")
    typer.echo(f"  max_position_pct: {settings.max_position_pct}")
    typer.echo(f"  daily_loss_limit_pct: {settings.daily_loss_limit_pct}")
    typer.echo(f"  max_open_positions: {settings.max_open_positions}")
    typer.echo(f"  stop_loss_pct: {settings.stop_loss_pct}")
    typer.echo(f"  max_correlation: {settings.max_correlation}")

    # Visual risk gauges for each setting
    try:
        console.print()
        console.print(Rule("[bold]Risk Gauges[/bold]"))
        console.print(f"  Position Size:    {_risk_gauge(settings.max_position_pct, 10.0)}")
        console.print(f"  Daily Loss Limit: {_risk_gauge(settings.daily_loss_limit_pct, 10.0)}")
        console.print(f"  Stop Loss:        {_risk_gauge(settings.stop_loss_pct, 15.0)}")
        console.print(f"  Max Correlation:  {_risk_gauge(settings.max_correlation, 1.0)}")
        console.print(
            f"  Open Positions:   {_risk_gauge(float(settings.max_open_positions), 20.0)}"
        )
    except Exception:
        pass  # Don't crash the command if gauge rendering fails


@app.command()
def limits(
    regime: str = typer.Option("medium", help="Volatility regime: low, medium, or high"),
) -> None:
    """Show regime-specific risk limits."""
    regime_enum = VolatilityRegime(regime.lower())
    regime_limits = REGIME_LIMITS[regime_enum]
    typer.echo(f"Regime Limits ({regime_enum.value.upper()})")
    for key, value in regime_limits.items():
        typer.echo(f"  {key}: {value}")

    # Regime comparison bar chart showing limits across all regimes
    try:
        console.print()
        console.print(Rule("[bold]Regime Comparison[/bold]"))
        regime_names = ["LOW", "MEDIUM", "HIGH"]
        regime_enums = [
            VolatilityRegime.LOW,
            VolatilityRegime.MEDIUM,
            VolatilityRegime.HIGH,
        ]

        setting_keys = [
            "max_position_pct",
            "daily_loss_limit_pct",
            "stop_loss_pct",
            "max_open_positions",
        ]
        for setting_key in setting_keys:
            labels = regime_names
            values = [float(REGIME_LIMITS[r][setting_key]) for r in regime_enums]
            chart = plotext_bar_chart(labels, values, title=setting_key)
            console.print(chart)
            console.print()
    except Exception:
        pass  # Don't crash the command if chart rendering fails
