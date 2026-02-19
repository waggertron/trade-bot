"""Portfolio CLI commands."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from src.cli.charts import (
    ascii_line_chart,
    plotext_bar_chart,
    spark_line,
)
from src.core.models import AssetType, OrderSide, Position

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="portfolio", help="Portfolio management commands.", no_args_is_help=True
)

console = Console()


def _example_positions() -> list[Position]:
    """Return example positions for demo output."""
    return [
        Position(
            symbol="AAPL",
            quantity=Decimal("50"),
            avg_entry_price=Decimal("178.25"),
            current_price=Decimal("185.40"),
            asset_type=AssetType.STOCK,
            sector="Technology",
        ),
        Position(
            symbol="GOOGL",
            quantity=Decimal("20"),
            avg_entry_price=Decimal("141.50"),
            current_price=Decimal("138.75"),
            asset_type=AssetType.STOCK,
            sector="Technology",
        ),
        Position(
            symbol="BTC-USD",
            quantity=Decimal("0.5"),
            avg_entry_price=Decimal("62000.00"),
            current_price=Decimal("67500.00"),
            asset_type=AssetType.CRYPTO,
        ),
        Position(
            symbol="MSFT",
            quantity=Decimal("30"),
            avg_entry_price=Decimal("415.00"),
            current_price=Decimal("422.80"),
            asset_type=AssetType.STOCK,
            sector="Technology",
        ),
    ]


def _example_trades() -> list[dict[str, object]]:
    """Return example trades for demo output."""
    now = datetime.now(timezone.utc)
    return [
        {
            "timestamp": now - timedelta(hours=2),
            "symbol": "AAPL",
            "side": OrderSide.BUY,
            "price": Decimal("178.25"),
            "quantity": Decimal("50"),
            "pnl": None,
        },
        {
            "timestamp": now - timedelta(hours=5),
            "symbol": "TSLA",
            "side": OrderSide.SELL,
            "price": Decimal("245.60"),
            "quantity": Decimal("15"),
            "pnl": Decimal("312.00"),
        },
        {
            "timestamp": now - timedelta(days=1),
            "symbol": "GOOGL",
            "side": OrderSide.BUY,
            "price": Decimal("141.50"),
            "quantity": Decimal("20"),
            "pnl": None,
        },
        {
            "timestamp": now - timedelta(days=1, hours=3),
            "symbol": "BTC-USD",
            "side": OrderSide.BUY,
            "price": Decimal("62000.00"),
            "quantity": Decimal("0.5"),
            "pnl": None,
        },
        {
            "timestamp": now - timedelta(days=2),
            "symbol": "MSFT",
            "side": OrderSide.BUY,
            "price": Decimal("415.00"),
            "quantity": Decimal("30"),
            "pnl": None,
        },
        {
            "timestamp": now - timedelta(days=3),
            "symbol": "NVDA",
            "side": OrderSide.SELL,
            "price": Decimal("890.50"),
            "quantity": Decimal("10"),
            "pnl": Decimal("1250.00"),
        },
        {
            "timestamp": now - timedelta(days=4),
            "symbol": "AMZN",
            "side": OrderSide.SELL,
            "price": Decimal("185.20"),
            "quantity": Decimal("25"),
            "pnl": Decimal("-180.50"),
        },
        {
            "timestamp": now - timedelta(days=5),
            "symbol": "META",
            "side": OrderSide.BUY,
            "price": Decimal("505.30"),
            "quantity": Decimal("12"),
            "pnl": None,
        },
    ]


@app.command()
def show() -> None:
    """Show current portfolio summary."""
    positions = _example_positions()
    cash = Decimal("55230.00")
    positions_value = sum(p.market_value for p in positions)
    total_value = cash + positions_value

    console.print()
    console.print(Rule("[bold]Portfolio Summary[/bold]"))
    console.print(f"  Total Value:      ${total_value:,.2f}")
    console.print(f"  Cash:             ${cash:,.2f}")
    console.print(f"  Positions Value:  ${positions_value:,.2f}")
    console.print()

    console.print(Rule("[bold]Positions[/bold]"))
    table = Table(title="Positions")
    table.add_column("Symbol", style="cyan")
    table.add_column("Qty", justify="right")
    table.add_column("Avg Entry", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Market Value", justify="right")
    table.add_column("Unrealized P&L", justify="right")
    table.add_column("Trend", justify="center")
    table.add_column("Type", justify="center")

    for pos in positions:
        pnl = pos.unrealized_pnl
        pnl_style = "green" if pnl >= 0 else "red"
        pnl_str = f"[{pnl_style}]${pnl:,.2f}[/{pnl_style}]"

        # Synthetic sparkline: simulate a recent price trend from entry to current
        try:
            entry = float(pos.avg_entry_price)
            current = float(pos.current_price)
            steps = 8
            trend_vals = [
                entry + (current - entry) * i / steps for i in range(steps + 1)
            ]
            trend_str = spark_line(trend_vals)
        except Exception:
            logger.debug("Chart render error", exc_info=True)
            trend_str = ""

        table.add_row(
            pos.symbol,
            f"{pos.quantity}",
            f"${pos.avg_entry_price:,.2f}",
            f"${pos.current_price:,.2f}",
            f"${pos.market_value:,.2f}",
            pnl_str,
            trend_str,
            pos.asset_type.value,
        )

    console.print(table)

    # --- Chart: Allocation horizontal bar chart ---
    console.print(Rule("[bold]Allocation[/bold]"))
    try:
        alloc_labels = [p.symbol for p in positions]
        alloc_values = [float(p.market_value) for p in positions]
        chart = plotext_bar_chart(
            alloc_labels,
            alloc_values,
            title="Portfolio Allocation by Market Value ($)",
        )
        console.print()
        console.print(Panel(chart, expand=False))
    except Exception:
        logger.debug("Chart render error", exc_info=True)

    # --- Chart: P&L bar chart per position ---
    console.print(Rule("[bold]Unrealized P&L[/bold]"))
    try:
        pnl_labels = [p.symbol for p in positions]
        pnl_values = [float(p.unrealized_pnl) for p in positions]
        chart = plotext_bar_chart(
            pnl_labels,
            pnl_values,
            title="Unrealized P&L per Position ($)",
        )
        console.print()
        console.print(Panel(chart, expand=False))
    except Exception:
        logger.debug("Chart render error", exc_info=True)


@app.command()
def trades(
    limit: int = typer.Option(20, help="Number of recent trades to show"),
) -> None:
    """Show recent trade history."""
    all_trades = _example_trades()
    display_trades = all_trades[:limit]

    console.print()
    console.print(Rule("[bold]Recent Trades[/bold]"))
    console.print(f"  Showing {len(display_trades)} trades")
    console.print()

    table = Table(title="Trade History")
    table.add_column("Timestamp", style="dim")
    table.add_column("Symbol", style="cyan")
    table.add_column("Side", justify="center")
    table.add_column("Price", justify="right")
    table.add_column("Quantity", justify="right")
    table.add_column("P&L", justify="right")

    for trade in display_trades:
        side = trade["side"]
        side_str = (
            f"[green]{side.value.upper()}[/green]"
            if side == OrderSide.BUY
            else f"[red]{side.value.upper()}[/red]"
        )

        pnl = trade["pnl"]
        if pnl is not None:
            pnl_style = "green" if pnl >= 0 else "red"
            pnl_str = f"[{pnl_style}]${pnl:,.2f}[/{pnl_style}]"
        else:
            pnl_str = "-"

        ts = trade["timestamp"]
        table.add_row(
            ts.strftime("%Y-%m-%d %H:%M"),
            str(trade["symbol"]),
            side_str,
            f"${trade['price']:,.2f}",
            f"{trade['quantity']}",
            pnl_str,
        )

    console.print(table)


@app.command()
def pnl(
    period: str = typer.Option("30d", help="P&L period (e.g. 7d, 30d, 90d)"),
) -> None:
    """Show P&L summary."""
    # Example P&L data for demo
    realized = Decimal("1381.50")
    unrealized = Decimal("3358.50")
    total = realized + unrealized
    winning_trades = 8
    losing_trades = 3
    total_trades = winning_trades + losing_trades
    win_rate = winning_trades / total_trades * 100

    console.print()
    console.print(Rule(f"[bold]P&L Summary[/bold] (period: {period})"))
    console.print()
    console.print(f"  Realized P&L:    [green]${realized:,.2f}[/green]")
    console.print(f"  Unrealized P&L:  [green]${unrealized:,.2f}[/green]")
    console.print(f"  Total P&L:       [green]${total:,.2f}[/green]")
    console.print()
    console.print(f"  Total Trades:    {total_trades}")
    console.print(f"  Winning Trades:  {winning_trades}")
    console.print(f"  Losing Trades:   {losing_trades}")
    console.print(f"  Win Rate:        {win_rate:.1f}%")

    # --- Chart: Synthetic equity curve from example P&L data ---
    console.print(Rule("[bold]Equity Curve[/bold]"))
    try:
        # Build a simple synthetic equity curve from available data
        base = 100_000.0
        equity_points = [base]
        avg_win_amount = float(realized) / winning_trades if winning_trades else 0
        avg_loss_amount = float(realized) * 0.3 / losing_trades if losing_trades else 0
        for i in range(total_trades):
            if i < winning_trades:
                equity_points.append(equity_points[-1] + avg_win_amount)
            else:
                equity_points.append(equity_points[-1] - avg_loss_amount)
        chart = ascii_line_chart(
            equity_points,
            title="Equity Curve (estimated from P&L)",
            height=10,
        )
        console.print()
        console.print(Panel(chart, expand=False))
    except Exception:
        logger.debug("Chart render error", exc_info=True)

    # --- Chart: Win/Loss distribution bar chart ---
    console.print(Rule("[bold]Win/Loss Distribution[/bold]"))
    try:
        chart = plotext_bar_chart(
            ["Winning Trades", "Losing Trades"],
            [winning_trades, losing_trades],
            title="Win / Loss Distribution",
        )
        console.print()
        console.print(Panel(chart, expand=False))
    except Exception:
        logger.debug("Chart render error", exc_info=True)
