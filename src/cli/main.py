"""Main entry point for the tradebot CLI."""

from __future__ import annotations

import typer

from src.cli.analytics_cmd import app as analytics_app
from src.cli.config_cmd import app as config_app
from src.cli.ml_cmd import app as ml_app
from src.cli.providers_cmd import app as providers_app
from src.cli.risk_cmd import app as risk_app
from src.cli.sentiment_cmd import app as sentiment_app

app = typer.Typer(name="tradebot", help="Trading bot CLI.", no_args_is_help=True)
app.add_typer(analytics_app, name="analytics")
app.add_typer(config_app, name="config")
app.add_typer(ml_app, name="ml")
app.add_typer(providers_app, name="providers")
app.add_typer(risk_app, name="risk")
app.add_typer(sentiment_app, name="sentiment")

if __name__ == "__main__":
    app()
