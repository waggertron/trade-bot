"""CLI commands for configuration management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.rule import Rule
from rich.tree import Tree

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

# Visual indicators for enabled/disabled boolean settings
_ENABLED = "[green]\u2705 enabled[/green]"
_DISABLED = "[red]\u274c disabled[/red]"


def _build_config_tree(data: Any, parent: Tree, key: str = "") -> None:
    """Recursively build a Rich Tree from a nested config dict.

    Booleans get visual enabled/disabled indicators. Lists are displayed
    inline. Nested dicts become subtrees.
    """
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                branch = parent.add(f"[bold cyan]{k}[/bold cyan]")
                _build_config_tree(v, branch, k)
            elif isinstance(v, list):
                items = ", ".join(str(i) for i in v)
                parent.add(f"[cyan]{k}:[/cyan] [yellow][{items}][/yellow]")
            elif isinstance(v, bool):
                indicator = _ENABLED if v else _DISABLED
                parent.add(f"[cyan]{k}:[/cyan] {indicator}")
            else:
                parent.add(f"[cyan]{k}:[/cyan] {v}")
    else:
        parent.add(f"{key}: {data}")


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
        raise typer.Exit(code=1) from None


@app.command()
def show(
    config: Annotated[
        str, typer.Option("--config", help="Path to settings YAML file.")
    ] = "config/settings.yaml",
    fmt: Annotated[
        str, typer.Option("--format", help="Output format: yaml, json, or tree.")
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
        raise typer.Exit(code=1) from None

    data = settings.model_dump(mode="json")
    if fmt != "json":
        console.print(Rule("[bold]Configuration[/bold]"))
    if fmt == "json":
        console.print(json.dumps(data, indent=2))
    elif fmt == "tree":
        try:
            tree = Tree(
                f"[bold white]Settings[/bold white] [dim]({path})[/dim]",
                guide_style="dim",
            )
            _build_config_tree(data, tree)
            console.print()
            console.print(tree)
            console.print()
        except Exception as exc:
            # Fall back to YAML if tree rendering fails
            console.print(f"[yellow]Tree rendering failed ({exc}), falling back to YAML.[/yellow]")
            console.print(yaml.dump(data, default_flow_style=False))
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
