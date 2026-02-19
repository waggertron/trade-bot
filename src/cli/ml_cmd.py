"""ML pipeline CLI commands."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from src.cli.charts import plotext_bar_chart

app = typer.Typer(name="ml", help="ML pipeline commands.", no_args_is_help=True)
console = Console()

# Feature categories used for the breakdown display.
_FEATURE_CATEGORIES: dict[str, list[str]] = {
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

# Example feature importance values (used when no model is loaded).
_EXAMPLE_FEATURE_IMPORTANCE: dict[str, float] = {
    "sma_14": 0.18,
    "rsi_14": 0.15,
    "sentiment_avg_6h": 0.13,
    "macd_signal": 0.11,
    "atr_14": 0.09,
    "btc_eth_corr_30d": 0.08,
    "price_zscore": 0.07,
    "volatility_regime": 0.06,
    "bbands_position": 0.05,
    "sma_5": 0.04,
    "sentiment_velocity": 0.04,
}


@app.command()
def status() -> None:
    """Show ML pipeline status summary."""
    console.print("[bold]ML Pipeline Status[/bold]")
    console.print("  Feature Store: (empty)")
    console.print("  Models: (none loaded)")
    console.print("  Use 'tradebot ml features --symbol <SYM>' to see stored features.")

    # Feature category breakdown as a Rich tree
    try:
        console.print()
        tree = Tree("[bold]Feature Categories[/bold]")
        for category, feats in _FEATURE_CATEGORIES.items():
            branch = tree.add(f"[cyan]{category}[/cyan] ({len(feats)} features)")
            for feat in feats:
                branch.add(f"[dim]{feat}[/dim]")
        console.print(tree)
    except Exception:
        pass  # Don't crash the command if tree rendering fails

    # Feature importance bar chart (example data)
    try:
        console.print()
        console.print("[bold]Feature Importance (example)[/bold]")
        # Sort by importance descending
        sorted_features = sorted(
            _EXAMPLE_FEATURE_IMPORTANCE.items(), key=lambda x: x[1], reverse=True
        )
        labels = [f[0] for f in sorted_features]
        values = [f[1] for f in sorted_features]
        chart = plotext_bar_chart(labels, values, title="Feature Importance")
        console.print(chart)
    except Exception:
        pass  # Don't crash the command if chart rendering fails


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
