"""Feature inspection CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="features", help="Feature inspection commands.", no_args_is_help=True
)

console = Console()

_FEATURES: dict[str, list[str]] = {
    "Technical": [
        "sma_5",
        "sma_14",
        "sma_50",
        "rsi_14",
        "macd_signal",
        "bbands_position",
        "atr_14",
    ],
    "Sentiment": [
        "sentiment_avg_6h",
        "sentiment_avg_24h",
        "sentiment_velocity",
        "article_volume_ratio",
    ],
    "Cross-asset": [
        "btc_eth_corr_30d",
        "btc_momentum_lead",
    ],
    "Regime": [
        "volatility_regime",
        "trend_regime",
    ],
    "On-chain": [
        "exchange_inflow_ratio",
        "active_addresses_trend",
        "onchain_tx_count",
    ],
}


@app.command("list")
def list_features() -> None:
    """List all available feature categories and names."""
    console.print()
    console.print("[bold]Available Features[/bold]")
    console.print()

    table = Table(title="Feature Catalog")
    table.add_column("Category", style="cyan")
    table.add_column("Feature Name")

    for category, features in _FEATURES.items():
        for idx, feature in enumerate(features):
            cat_label = category if idx == 0 else ""
            table.add_row(cat_label, feature)

    console.print(table)


@app.command()
def status() -> None:
    """Show feature engine status."""
    num_categories = len(_FEATURES)
    total_features = sum(len(feats) for feats in _FEATURES.values())

    console.print()
    console.print("[bold]Feature Engine Status[/bold]")
    console.print()
    console.print(f"  Categories:     {num_categories}")
    console.print(f"  Total Features: {total_features}")
    console.print(f"  Status:         Ready")
