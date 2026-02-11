"""Main entry point for the tradebot CLI."""

from __future__ import annotations

import typer

from src.cli.config_cmd import app as config_app

app = typer.Typer(name="tradebot", help="Trading bot CLI.", no_args_is_help=True)
app.add_typer(config_app, name="config")

if __name__ == "__main__":
    app()
