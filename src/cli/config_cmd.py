"""CLI commands for configuration management."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console

from src.core.config import (
    AISettings,
    DashboardSettings,
    RiskSettings,
    Settings,
    SymbolsConfig,
    TradingSettings,
)
from src.providers.configs import (
    BinanceMarketConfig,
    ClaudeSentimentConfig,
    KrakenMarketConfig,
    MockMarketConfig,
    MockNewsConfig,
    MockSentimentConfig,
    NewsAPIConfig,
    OllamaSentimentConfig,
    RSSConfig,
)

app = typer.Typer(name="config", help="Configuration management commands.", no_args_is_help=True)
console = Console()

CONFIG_MODELS: dict[str, type] = {
    "RiskSettings": RiskSettings,
    "Settings": Settings,
    "TradingSettings": TradingSettings,
    "SymbolsConfig": SymbolsConfig,
    "AISettings": AISettings,
    "DashboardSettings": DashboardSettings,
    "KrakenMarketConfig": KrakenMarketConfig,
    "BinanceMarketConfig": BinanceMarketConfig,
    "MockMarketConfig": MockMarketConfig,
    "RSSConfig": RSSConfig,
    "NewsAPIConfig": NewsAPIConfig,
    "MockNewsConfig": MockNewsConfig,
    "OllamaSentimentConfig": OllamaSentimentConfig,
    "ClaudeSentimentConfig": ClaudeSentimentConfig,
    "MockSentimentConfig": MockSentimentConfig,
}


@app.command()
def validate(
    config: Annotated[
        str, typer.Option("--config", help="Path to settings YAML file.")
    ] = "config/settings.yaml",
) -> None:
    """Validate a settings YAML file."""
    path = Path(config)
    if not path.exists():
        console.print(f"[red]Error:[/red] File not found: {path}")
        raise typer.Exit(code=1)
    try:
        Settings.from_yaml(path)
        console.print(f"[green]Config is valid:[/green] {path}")
    except (ValidationError, Exception) as exc:
        console.print(f"[red]Validation error:[/red] {exc}")
        raise typer.Exit(code=1)


@app.command()
def show(
    config: Annotated[
        str, typer.Option("--config", help="Path to settings YAML file.")
    ] = "config/settings.yaml",
    fmt: Annotated[
        str, typer.Option("--format", help="Output format: yaml or json.")
    ] = "yaml",
) -> None:
    """Load and display the current configuration."""
    path = Path(config)
    if not path.exists():
        console.print(f"[red]Error:[/red] File not found: {path}")
        raise typer.Exit(code=1)
    try:
        settings = Settings.from_yaml(path)
    except (ValidationError, Exception) as exc:
        console.print(f"[red]Validation error:[/red] {exc}")
        raise typer.Exit(code=1)

    data = settings.model_dump(mode="json")
    if fmt == "json":
        console.print(json.dumps(data, indent=2))
    else:
        console.print(yaml.dump(data, default_flow_style=False))


@app.command()
def schema(
    model_name: Annotated[str, typer.Argument(help="Name of the config model.")],
) -> None:
    """Print the JSON schema for a configuration model."""
    if model_name not in CONFIG_MODELS:
        console.print(
            f"[red]Error:[/red] Unknown model '{model_name}'. "
            f"Available: {', '.join(sorted(CONFIG_MODELS))}"
        )
        raise typer.Exit(code=1)
    model_cls = CONFIG_MODELS[model_name]
    console.print(json.dumps(model_cls.model_json_schema(), indent=2))
