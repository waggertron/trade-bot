"""CLI commands for the simulation system."""
from __future__ import annotations

import asyncio
import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.core.config import RiskLevel

app = typer.Typer(help="Simulation system: run walk-forward backtests and Monte Carlo projections.")
console = Console()


@app.callback()
def callback() -> None:
    """Simulation system: run walk-forward backtests and Monte Carlo projections."""

ALL_STOCKS = [
    "SPY", "QQQ", "DIA", "IWM",
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "XLF", "XLK", "XLE", "XLV", "XLI",
]


def _run_simulation(
    stocks: list[str],
    balance: float,
    train_days: int,
    test_days: int,
    risk_levels: list[RiskLevel],
    mc_sims: int,
) -> dict:
    """Run the simulation engine and return the report as a dict."""
    from src.simulation.engine import SimulationEngine
    from src.simulation.models import SimulationConfig

    config = SimulationConfig(
        stocks=stocks,
        initial_balance=balance,
        train_days=train_days,
        test_days=test_days,
        risk_levels=risk_levels,
        mc_simulations=mc_sims,
    )
    engine = SimulationEngine(config)
    report = asyncio.run(engine.run())
    return report.model_dump()


@app.command()
def run(
    stocks: Optional[list[str]] = typer.Option(None, help="Stock symbols (default: all 16)"),
    balance: float = typer.Option(10_000.0, help="Starting balance in USD"),
    train_days: int = typer.Option(60, help="Training window in days"),
    test_days: int = typer.Option(30, help="Test/simulation window in days"),
    risk_levels: Optional[list[str]] = typer.Option(None, "--risk", help="Risk levels (default: all)"),
    mc_sims: int = typer.Option(1000, help="Number of Monte Carlo simulations"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Run a full simulation across stocks and risk levels."""
    stock_list = stocks or ALL_STOCKS
    levels = [RiskLevel(r) for r in risk_levels] if risk_levels else list(RiskLevel)

    console.print(f"\n[bold]Simulation: {len(stock_list)} stocks, {len(levels)} risk levels[/bold]")
    console.print(f"Balance: ${balance:,.0f} | Train: {train_days}d | Test: {test_days}d | MC paths: {mc_sims}\n")

    with console.status("[bold green]Running simulation..."):
        report = _run_simulation(stock_list, balance, train_days, test_days, levels, mc_sims)

    if output_json:
        console.print(json.dumps(report, indent=2, default=str))
        return

    _print_report(report)


def _print_report(report: dict) -> None:
    """Pretty-print simulation results."""
    console.print(f"\n[bold green]Simulation {report['id']} — {report['status']}[/bold green]\n")

    # Risk level comparison table
    table = Table(title="Risk Level Comparison")
    table.add_column("Risk Level", style="bold")
    table.add_column("Avg Return %", justify="right")
    table.add_column("Avg Sharpe", justify="right")
    table.add_column("Avg Max DD %", justify="right")
    table.add_column("Total Trades", justify="right")

    for level_name, result in report.get("risk_level_results", {}).items():
        ret_style = "green" if result["total_return_pct"] >= 0 else "red"
        table.add_row(
            level_name,
            f"[{ret_style}]{result['total_return_pct']:.2f}%[/{ret_style}]",
            f"{result['avg_sharpe']:.3f}",
            f"{result['avg_max_drawdown']:.2f}%",
            str(result["total_trades"]),
        )

    console.print(table)

    # Per-stock details for each risk level
    for level_name, result in report.get("risk_level_results", {}).items():
        if not result.get("stock_results"):
            continue

        stock_table = Table(title=f"\n{level_name.upper()} — Per-Stock Results")
        stock_table.add_column("Symbol", style="bold")
        stock_table.add_column("Return %", justify="right")
        stock_table.add_column("Sharpe", justify="right")
        stock_table.add_column("Max DD %", justify="right")
        stock_table.add_column("Win Rate", justify="right")
        stock_table.add_column("Trades", justify="right")

        for sr in result["stock_results"]:
            ret_style = "green" if sr["return_pct"] >= 0 else "red"
            stock_table.add_row(
                sr["symbol"],
                f"[{ret_style}]{sr['return_pct']:.2f}%[/{ret_style}]",
                f"{sr['sharpe_ratio']:.3f}",
                f"{sr['max_drawdown']:.2f}%",
                f"{sr['win_rate']:.1%}",
                str(sr["total_trades"]),
            )

        console.print(stock_table)

    # Monte Carlo projections
    for level_name, result in report.get("risk_level_results", {}).items():
        if not result.get("monte_carlo_projections"):
            continue

        mc_table = Table(title=f"\n{level_name.upper()} — Monte Carlo Projections ({report['config']['test_days']}d forward)")
        mc_table.add_column("Symbol", style="bold")
        mc_table.add_column("Median Final", justify="right")
        mc_table.add_column("P5 Final", justify="right")
        mc_table.add_column("P95 Final", justify="right")
        mc_table.add_column("Median Return %", justify="right")
        mc_table.add_column("Worst DD (P95) %", justify="right")

        for mc in result["monte_carlo_projections"]:
            mc_table.add_row(
                mc["symbol"],
                f"${mc['median_final']:,.2f}",
                f"${mc['p5_final']:,.2f}",
                f"${mc['p95_final']:,.2f}",
                f"{mc['median_return_pct']:.2f}%",
                f"{mc['worst_drawdown_p95']:.2f}%",
            )

        console.print(mc_table)

    # Recommendation
    rec = report.get("recommendation")
    if rec:
        console.print(f"\n[bold yellow]RECOMMENDATION[/bold yellow]")
        console.print(f"  Optimal Risk Level: [bold]{rec['optimal_risk_level']}[/bold]")
        console.print(f"  Confidence: {rec['confidence']:.0%}")
        console.print(f"  Reasoning: {rec['reasoning']}")
        if rec.get("suggested_weights"):
            console.print(f"  Strategy Weights: {rec['suggested_weights']}")
        console.print()
