"""Backtesting CLI commands."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

import typer
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from src.analytics.attribution import StrategyAttribution
from src.analytics.models import AttributedFill
from src.analytics.monte_carlo import MonteCarloSimulator
from src.analytics.reporter import AnalyticsReporter
from src.cli.charts import ascii_line_chart, plotext_bar_chart
from src.core.models import Fill, OrderSide

app = typer.Typer(
    name="backtest", help="Backtesting commands.", no_args_is_help=True
)

console = Console()


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

    console.print(Rule("[bold]Backtest Report[/bold]"))
    report = reporter.generate_report(fills, initial_cash)
    typer.echo(report)

    # --- Charts (best-effort, don't crash the command) ---
    console.print(Rule("[bold]Charts[/bold]"))
    _print_backtest_charts(fills, initial_cash, attribution)


def _pair_fills_into_trades(
    fills: list[AttributedFill],
) -> list[dict[str, object]]:
    """FIFO pairing of fills into trade dicts with pnl and strategy."""
    buys: dict[str, list[AttributedFill]] = defaultdict(list)
    sells: dict[str, list[AttributedFill]] = defaultdict(list)

    for af in fills:
        if af.fill.side == OrderSide.BUY:
            buys[af.fill.symbol].append(af)
        else:
            sells[af.fill.symbol].append(af)

    trades: list[dict[str, object]] = []
    for symbol in buys:
        buy_q = list(buys[symbol])
        sell_q = list(sells.get(symbol, []))
        bi, si = 0, 0
        while bi < len(buy_q) and si < len(sell_q):
            bf = buy_q[bi]
            sf = sell_q[si]
            entry = float(bf.fill.fill_price)
            exit_ = float(sf.fill.fill_price)
            qty = float(min(bf.fill.quantity, sf.fill.quantity))
            pnl = (exit_ - entry) * qty
            trades.append(
                {
                    "symbol": symbol,
                    "pnl": pnl,
                    "strategy": bf.strategy,
                }
            )
            bi += 1
            si += 1
    return trades


def _print_backtest_charts(
    fills: list[AttributedFill],
    initial_cash: float,
    attribution: StrategyAttribution,
) -> None:
    """Render charts for the example backtest (best-effort)."""
    trades = _pair_fills_into_trades(fills)
    if not trades:
        return

    # --- Chart: Equity curve ---
    console.print(Rule("[bold]Equity Curve[/bold]"))
    try:
        equity = [initial_cash]
        running = initial_cash
        for t in trades:
            running += float(t["pnl"])
            equity.append(running)
        chart = ascii_line_chart(equity, title="Equity Curve", height=10)
        console.print()
        console.print(Panel(chart, expand=False))
    except Exception:
        pass

    # --- Chart: Strategy attribution bar chart ---
    console.print(Rule("[bold]Strategy Attribution[/bold]"))
    try:
        strat_pnl: dict[str, float] = defaultdict(float)
        for t in trades:
            strat_pnl[str(t["strategy"])] += float(t["pnl"])
        if strat_pnl:
            chart = plotext_bar_chart(
                list(strat_pnl.keys()),
                list(strat_pnl.values()),
                title="Strategy Attribution (P&L $)",
            )
            console.print()
            console.print(Panel(chart, expand=False))
    except Exception:
        pass

    # --- Chart: Drawdown chart (inverted) ---
    console.print(Rule("[bold]Drawdown[/bold]"))
    try:
        equity = [initial_cash]
        running = initial_cash
        for t in trades:
            running += float(t["pnl"])
            equity.append(running)

        # Compute drawdown series as negative values
        peak = equity[0]
        drawdowns: list[float] = []
        for val in equity:
            if val > peak:
                peak = val
            dd = ((peak - val) / peak * 100.0) if peak > 0 else 0.0
            drawdowns.append(-dd)  # negative so chart goes downward

        chart = ascii_line_chart(drawdowns, title="Drawdown % (inverted)", height=8)
        console.print()
        console.print(Panel(chart, expand=False))
    except Exception:
        pass
