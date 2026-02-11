"""Risk management CLI commands."""

from __future__ import annotations

import typer

from src.agents.risk_manager import REGIME_LIMITS
from src.core.config import RiskSettings
from src.risk.models import VolatilityRegime

app = typer.Typer(
    name="risk", help="Risk management commands.", no_args_is_help=True
)


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
