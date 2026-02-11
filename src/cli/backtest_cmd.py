"""Backtesting CLI commands."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import typer

from src.analytics.attribution import StrategyAttribution
from src.analytics.models import AttributedFill
from src.analytics.monte_carlo import MonteCarloSimulator
from src.analytics.reporter import AnalyticsReporter
from src.core.models import Fill, OrderSide

app = typer.Typer(
    name="backtest", help="Backtesting commands.", no_args_is_help=True
)


@app.command()
def status() -> None:
    """Show backtester module summary."""
    typer.echo("Backtest Module")
    typer.echo("  Available analyzers:")
    typer.echo("    - StrategyAttribution")
    typer.echo("    - MonteCarloSimulator")
    typer.echo("    - RegimeTagger")
    typer.echo("  Report generator: AnalyticsReporter")
    typer.echo("  Status: Ready")


def _example_fills() -> list[AttributedFill]:
    """Build example fills for the demo backtest."""
    now = datetime.now(timezone.utc)

    return [
        # --- momentum strategy: AAPL buy then sell (profitable) ---
        AttributedFill(
            fill=Fill(
                order_id="o1",
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=Decimal("50"),
                fill_price=Decimal("170.00"),
                timestamp=now,
            ),
            strategy="momentum",
            regime="low",
        ),
        AttributedFill(
            fill=Fill(
                order_id="o2",
                symbol="AAPL",
                side=OrderSide.SELL,
                quantity=Decimal("50"),
                fill_price=Decimal("185.00"),
                timestamp=now,
            ),
            strategy="momentum",
            regime="low",
        ),
        # --- sentiment strategy: GOOGL buy then sell (small loss) ---
        AttributedFill(
            fill=Fill(
                order_id="o3",
                symbol="GOOGL",
                side=OrderSide.BUY,
                quantity=Decimal("30"),
                fill_price=Decimal("142.00"),
                timestamp=now,
            ),
            strategy="sentiment",
            regime="medium",
        ),
        AttributedFill(
            fill=Fill(
                order_id="o4",
                symbol="GOOGL",
                side=OrderSide.SELL,
                quantity=Decimal("30"),
                fill_price=Decimal("138.50"),
                timestamp=now,
            ),
            strategy="sentiment",
            regime="medium",
        ),
        # --- quantitative strategy: MSFT buy then sell (profitable) ---
        AttributedFill(
            fill=Fill(
                order_id="o5",
                symbol="MSFT",
                side=OrderSide.BUY,
                quantity=Decimal("20"),
                fill_price=Decimal("410.00"),
                timestamp=now,
            ),
            strategy="quantitative",
            regime="low",
        ),
        AttributedFill(
            fill=Fill(
                order_id="o6",
                symbol="MSFT",
                side=OrderSide.SELL,
                quantity=Decimal("20"),
                fill_price=Decimal("425.00"),
                timestamp=now,
            ),
            strategy="quantitative",
            regime="low",
        ),
        # --- momentum strategy: NVDA buy then sell (profitable) ---
        AttributedFill(
            fill=Fill(
                order_id="o7",
                symbol="NVDA",
                side=OrderSide.BUY,
                quantity=Decimal("15"),
                fill_price=Decimal("850.00"),
                timestamp=now,
            ),
            strategy="momentum",
            regime="medium",
        ),
        AttributedFill(
            fill=Fill(
                order_id="o8",
                symbol="NVDA",
                side=OrderSide.SELL,
                quantity=Decimal("15"),
                fill_price=Decimal("890.00"),
                timestamp=now,
            ),
            strategy="momentum",
            regime="medium",
        ),
    ]


@app.command()
def example() -> None:
    """Run a quick example backtest using in-memory data (no DB needed)."""
    fills = _example_fills()
    initial_cash = 100_000.0

    attribution = StrategyAttribution()
    simulator = MonteCarloSimulator(n_simulations=100, seed=42)
    reporter = AnalyticsReporter(attribution=attribution, simulator=simulator)

    report = reporter.generate_report(fills, initial_cash)
    typer.echo(report)
