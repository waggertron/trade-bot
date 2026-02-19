"""CLI commands for the simulation system."""
from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.charts import (
    ascii_line_chart,
    format_pct,
    plotext_bar_chart,
    plotext_heatmap,
    plotext_multi_line,
)
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
    portfolio_mode: bool = False,
    allocation_weights: dict[str, float] | None = None,
    rebalance_freq: str = "none",
    seed: int | None = None,
    rebalance_threshold: float = 5.0,
) -> dict:
    """Run the simulation engine and return the report as a dict."""
    from src.simulation.engine import SimulationEngine
    from src.simulation.models import AllocationWeights, RebalanceConfig, SimulationConfig

    allocation = AllocationWeights(
        mode="custom" if allocation_weights else "equal_weight",
        weights=allocation_weights or {},
    )
    rebalance = RebalanceConfig(frequency=rebalance_freq, threshold_pct=rebalance_threshold)

    config = SimulationConfig(
        stocks=stocks,
        initial_balance=balance,
        train_days=train_days,
        test_days=test_days,
        risk_levels=risk_levels,
        mc_simulations=mc_sims,
        mc_seed=seed,
        portfolio_mode=portfolio_mode,
        allocation=allocation,
        rebalance=rebalance,
    )
    engine = SimulationEngine(config)
    report = asyncio.run(engine.run())
    return report.model_dump()


@app.command()
def run(
    stocks: list[str] | None = typer.Option(None, help="Stock symbols (default: all 16)"),
    balance: float = typer.Option(10_000.0, help="Starting balance in USD"),
    train_days: int = typer.Option(60, help="Training window in days"),
    test_days: int = typer.Option(30, help="Test/simulation window in days"),
    risk_levels: list[str] | None = typer.Option(None, "--risk", help="Risk levels (default: all)"),
    mc_sims: int = typer.Option(1000, help="Number of Monte Carlo simulations"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
    portfolio: bool = typer.Option(False, "--portfolio", help="Enable portfolio simulation mode"),
    weights: str | None = typer.Option(
        None, "--weights", help='Custom weights JSON',
    ),
    rebalance: str = typer.Option(
        "none", "--rebalance", help="none|daily|weekly|monthly",
    ),
    seed: int | None = typer.Option(None, "--seed", help="Monte Carlo random seed (default: random)"),
    rebalance_threshold: float = typer.Option(5.0, "--rebalance-threshold", help="Rebalance drift threshold %"),
) -> None:
    """Run a full simulation across stocks and risk levels."""
    stock_list = stocks or ALL_STOCKS
    levels = [RiskLevel(r) for r in risk_levels] if risk_levels else list(RiskLevel)

    allocation_weights = json.loads(weights) if weights else None

    console.print(f"\n[bold]Simulation: {len(stock_list)} stocks, {len(levels)} risk levels[/bold]")
    console.print(
        f"Balance: ${balance:,.0f} | Train: {train_days}d"
        f" | Test: {test_days}d | MC paths: {mc_sims}"
    )
    if seed is not None:
        console.print(f"Seed: {seed}")
    if portfolio:
        console.print(f"  Portfolio Mode: [bold green]ON[/bold green] | Rebalance: {rebalance}")
    console.print()

    with console.status("[bold green]Running simulation..."):
        report = _run_simulation(
            stock_list, balance, train_days, test_days, levels, mc_sims,
            portfolio_mode=portfolio,
            allocation_weights=allocation_weights,
            rebalance_freq=rebalance,
            seed=seed,
            rebalance_threshold=rebalance_threshold,
        )

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

        # --- Portfolio Equity Curve chart ---
        pm = result.get("portfolio_metrics")
        if pm:
            curve = pm.get("equity_curve", [])
            if len(curve) >= 2:
                try:
                    chart = ascii_line_chart(
                        curve,
                        title=f"{level_name.upper()} | Portfolio Equity Curve",
                        height=10,
                    )
                    console.print(Panel(chart, expand=False))
                except Exception:
                    pass  # chart rendering is best-effort

        # --- Portfolio Metrics panel ---
        if pm:
            metrics_table = Table(title=f"{level_name.upper()} — Portfolio Metrics")
            metrics_table.add_column("Metric", style="bold")
            metrics_table.add_column("Value", justify="right")
            metrics_table.add_row("Initial Balance", f"${pm['initial_balance']:,.2f}")
            metrics_table.add_row("Final Value", f"${pm['final_value']:,.2f}")
            metrics_table.add_row("Total Return", format_pct(pm["total_return_pct"]))
            metrics_table.add_row("Max Drawdown", f"{pm['max_drawdown']:.2f}%")
            metrics_table.add_row("Sharpe Ratio", f"{pm['sharpe_ratio']:.3f}")
            metrics_table.add_row("Sortino Ratio", f"{pm['sortino_ratio']:.3f}")
            metrics_table.add_row("Calmar Ratio", f"{pm['calmar_ratio']:.3f}")
            metrics_table.add_row("Total Trades", str(pm["total_trades"]))
            console.print(metrics_table)

        # --- Allocation display ---
        config = report.get("config", {})
        if config.get("portfolio_mode"):
            alloc = config.get("allocation", {})
            weights_dict = alloc.get("weights", {})
            mode = alloc.get("mode", "equal_weight")
            if mode == "equal_weight" and result.get("stock_results"):
                n = len(result["stock_results"])
                symbols = [sr["symbol"] for sr in result["stock_results"]]
                weights_str = " | ".join(f"{s}: {100/n:.1f}%" for s in symbols)
            elif weights_dict:
                weights_str = " | ".join(f"{s}: {w*100:.1f}%" for s, w in weights_dict.items())
            else:
                weights_str = "N/A"
            console.print(f"\n  [bold]Allocation:[/bold] {weights_str}")

        # --- Portfolio Monte Carlo projection summary ---
        pmc = result.get("portfolio_monte_carlo")
        if pmc:
            pmc_table = Table(title=f"{level_name.upper()} — Portfolio Monte Carlo Projection")
            pmc_table.add_column("Metric", style="bold")
            pmc_table.add_column("Value", justify="right")
            pmc_table.add_row("Median Final", f"${pmc['median_final']:,.2f}")
            pmc_table.add_row("P5 Final", f"${pmc['p5_final']:,.2f}")
            pmc_table.add_row("P95 Final", f"${pmc['p95_final']:,.2f}")
            pmc_table.add_row("Median Return %", f"{pmc['median_return_pct']:.2f}%")
            pmc_table.add_row("Worst DD (P95)", f"{pmc['worst_drawdown_p95']:.2f}%")
            console.print(pmc_table)

        # --- Correlation matrix ---
        if pmc and pmc.get("correlation_matrix"):
            corr = pmc["correlation_matrix"]
            corr_table = Table(title="Return Correlation Matrix")
            corr_table.add_column("")
            symbols = [sr["symbol"] for sr in result.get("stock_results", [])]
            for sym in symbols:
                corr_table.add_column(sym, justify="right")
            for i, row in enumerate(corr):
                label = symbols[i] if i < len(symbols) else str(i)
                corr_table.add_row(label, *[f"{v:.3f}" for v in row])
            console.print(corr_table)

    # Monte Carlo projections
    for level_name, result in report.get("risk_level_results", {}).items():
        if not result.get("monte_carlo_projections"):
            continue

        test_d = report['config']['test_days']
        mc_table = Table(
            title=f"\n{level_name.upper()} — MC Projections ({test_d}d forward)",
        )
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

    # --- Charts: Equity curve per stock (first risk level with stock results) ---
    try:
        for level_name, result in report.get("risk_level_results", {}).items():
            for sr in result.get("stock_results") or []:
                curve = sr.get("equity_curve", [])
                if len(curve) >= 2:
                    chart = ascii_line_chart(
                        curve,
                        title=f"{level_name.upper()} | {sr['symbol']} Equity Curve",
                        height=10,
                    )
                    console.print(Panel(chart, expand=False))
    except Exception:
        pass  # chart rendering is best-effort

    # --- Chart: Return comparison bar chart across risk levels ---
    try:
        rl_results = report.get("risk_level_results", {})
        if rl_results:
            rl_labels = list(rl_results.keys())
            rl_returns = [rl_results[k]["total_return_pct"] for k in rl_labels]
            chart = plotext_bar_chart(
                rl_labels,
                rl_returns,
                title="Return % by Risk Level",
            )
            console.print()
            console.print(Panel(chart, expand=False))
    except Exception:
        pass

    # --- Chart: Monte Carlo projection cone (P5 / Median / P95) per risk level ---
    try:
        for level_name, result in report.get("risk_level_results", {}).items():
            mc_list = result.get("monte_carlo_projections") or []
            if mc_list:
                series: dict[str, list[float]] = {
                    "P5": [],
                    "Median": [],
                    "P95": [],
                }
                symbols: list[str] = []
                for mc in mc_list:
                    symbols.append(mc["symbol"])
                    series["P5"].append(mc["p5_final"])
                    series["Median"].append(mc["median_final"])
                    series["P95"].append(mc["p95_final"])
                chart = plotext_multi_line(
                    series,
                    title=f"{level_name.upper()} | Monte Carlo Projection Cone",
                )
                console.print()
                console.print(Panel(chart, expand=False))
    except Exception:
        pass

    # --- Chart: Win rate heatmap (stocks x risk levels) ---
    try:
        rl_results = report.get("risk_level_results", {})
        if rl_results:
            risk_labels = list(rl_results.keys())
            # Collect all unique stock symbols across risk levels
            all_symbols: list[str] = []
            for rl in rl_results.values():
                for sr in rl.get("stock_results") or []:
                    if sr["symbol"] not in all_symbols:
                        all_symbols.append(sr["symbol"])

            if all_symbols:
                # Build matrix: rows = stocks, cols = risk levels
                matrix: list[list[float]] = []
                for sym in all_symbols:
                    row: list[float] = []
                    for rl_name in risk_labels:
                        rl = rl_results[rl_name]
                        wr = 0.0
                        for sr in rl.get("stock_results") or []:
                            if sr["symbol"] == sym:
                                wr = sr.get("win_rate", 0.0) * 100.0
                                break
                        row.append(wr)
                    matrix.append(row)

                chart = plotext_heatmap(
                    matrix,
                    row_labels=all_symbols,
                    col_labels=risk_labels,
                    title="Win Rate % (Stocks x Risk Levels)",
                )
                console.print()
                console.print(Panel(chart, expand=False))
    except Exception:
        pass

    # Recommendation
    rec = report.get("recommendation")
    if rec:
        console.print("\n[bold yellow]RECOMMENDATION[/bold yellow]")
        console.print(f"  Optimal Risk Level: [bold]{rec['optimal_risk_level']}[/bold]")
        console.print(f"  Confidence: {rec['confidence']:.0%}")
        console.print(f"  Reasoning: {rec['reasoning']}")
        if rec.get("suggested_weights"):
            console.print(f"  Strategy Weights: {rec['suggested_weights']}")
        console.print()
