"""CLI commands for the simulation system."""

from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

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
    "SPY",
    "QQQ",
    "DIA",
    "IWM",
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "TSLA",
    "XLF",
    "XLK",
    "XLE",
    "XLV",
    "XLI",
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
    max_position_pct: float | None = None,
    progress_cb=None,
    use_cache: bool = True,
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
        max_position_pct=max_position_pct,
        portfolio_mode=portfolio_mode,
        allocation=allocation,
        rebalance=rebalance,
    )

    # Check report cache on hit (only when cache enabled and seed is set)
    report_cache = None
    if use_cache and seed is not None:
        from src.simulation.cache import ReportCache

        report_cache = ReportCache()
        cached = report_cache.get(config)
        if cached is not None:
            return cached

    engine = SimulationEngine(config, progress_cb=progress_cb, use_cache=use_cache)
    report = asyncio.run(engine.run())
    result = report.model_dump()

    if report_cache is not None:
        report_cache.put(config, result)

    return result


@app.command()
def run(
    stocks: list[str] | None = typer.Option(None, help="Stock symbols (default: all 16)"),  # noqa: B008
    balance: float = typer.Option(10_000.0, help="Starting balance in USD"),
    train_days: int = typer.Option(60, help="Training window in days"),
    test_days: int = typer.Option(30, help="Test/simulation window in days"),
    risk_levels: list[str] | None = typer.Option(None, "--risk", help="Risk levels (default: all)"),  # noqa: B008
    mc_sims: int = typer.Option(1000, help="Number of Monte Carlo simulations"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
    portfolio: bool = typer.Option(False, "--portfolio", help="Enable portfolio simulation mode"),
    weights: str | None = typer.Option(
        None,
        "--weights",
        help="Custom weights JSON",
    ),
    rebalance: list[str] = typer.Option(  # noqa: B008
        ["none"],
        "--rebalance",
        help="Rebalance modes: none, daily, weekly, monthly (repeat for comparison)",
    ),
    seed: int | None = typer.Option(
        None,
        "--seed",
        help="Monte Carlo random seed (default: random)",
    ),
    rebalance_threshold: float = typer.Option(
        5.0,
        "--rebalance-threshold",
        help="Rebalance drift threshold %",
    ),
    max_position_pct: float | None = typer.Option(
        None,
        "--max-position-pct",
        help="Override max position size %",
    ),
    charts: str = typer.Option("summary", "--charts", help="Chart detail: none, summary, full"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable disk cache"),
) -> None:
    """Run a full simulation across stocks and risk levels."""
    stock_list = stocks or ALL_STOCKS
    levels = [RiskLevel(r) for r in risk_levels] if risk_levels else list(RiskLevel)

    allocation_weights = json.loads(weights) if weights else None

    # Use stderr for status when JSON output is requested
    import sys

    status_console = Console(stderr=True) if output_json else console

    status_console.print(
        f"\n[bold]Simulation: {len(stock_list)} stocks, {len(levels)} risk levels[/bold]"
    )
    status_console.print(
        f"Balance: ${balance:,.0f} | Train: {train_days}d"
        f" | Test: {test_days}d | MC paths: {mc_sims}"
    )
    if seed is not None:
        status_console.print(f"Seed: {seed}")
    if max_position_pct is not None:
        status_console.print(f"Max Position Size: {max_position_pct}%")
    if no_cache:
        status_console.print("Cache: DISABLED")
    if portfolio:
        rebal_display = ", ".join(rebalance)
        status_console.print(
            f"  Portfolio Mode: [bold green]ON[/bold green] | Rebalance: {rebal_display}"
        )
    status_console.print()

    num_stocks = len(stock_list)
    reports: dict[str, dict] = {}

    for rebal_mode in rebalance:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=status_console,
        ) as progress:
            risk_task = progress.add_task("Risk levels", total=len(levels))
            stock_task = progress.add_task("Stocks", total=num_stocks)

            def on_progress(
                stage: str,
                current: int,
                total: int,
                detail: str = "",
                _risk_task=risk_task,
                _stock_task=stock_task,
            ) -> None:
                if stage == "risk_level":
                    progress.update(_risk_task, completed=current, description=f"Risk: {detail}")
                    progress.update(_stock_task, completed=0, total=num_stocks)
                elif stage == "stock":
                    progress.update(_stock_task, completed=current, description=f"Stock: {detail}")
                elif stage == "benchmark":
                    progress.update(_risk_task, description="SPY benchmarks")

            report = _run_simulation(
                stock_list,
                balance,
                train_days,
                test_days,
                levels,
                mc_sims,
                portfolio_mode=portfolio,
                allocation_weights=allocation_weights,
                rebalance_freq=rebal_mode,
                seed=seed,
                rebalance_threshold=rebalance_threshold,
                max_position_pct=max_position_pct,
                progress_cb=on_progress,
                use_cache=not no_cache,
            )
            progress.update(risk_task, completed=len(levels))
            progress.update(stock_task, completed=num_stocks)

        reports[rebal_mode] = report

    if output_json:
        output = reports if len(reports) > 1 else next(iter(reports.values()))
        sys.stdout.write(json.dumps(output, indent=2, default=str))
        sys.stdout.write("\n")
        return

    if len(reports) == 1:
        _print_report(next(iter(reports.values())), charts_mode=charts)
    else:
        for mode, report in reports.items():
            console.print(Rule(f"[bold]Rebalance: {mode}[/bold]"))
            _print_report(report, charts_mode=charts)
        _print_rebalance_comparison(reports)


def _print_report(report: dict, *, charts_mode: str = "summary") -> None:
    """Pretty-print simulation results."""
    console.print(f"\n[bold green]Simulation {report['id']} — {report['status']}[/bold green]\n")

    console.print(Rule("[bold]Risk Level Comparison[/bold]"))

    # Risk level comparison table
    table = Table(title="Risk Level Comparison")
    table.add_column("Risk Level", style="bold")
    table.add_column("Avg Return %", justify="right")
    table.add_column("Avg Sharpe", justify="right")
    table.add_column("Avg Max DD %", justify="right")
    table.add_column("Total Trades", justify="right")

    for level_name, result in report.get("risk_level_results", {}).items():
        ret_style = "green" if result["total_return_pct"] >= 0 else "red"
        sh_style = "green" if result["avg_sharpe"] >= 0 else "red"
        table.add_row(
            level_name,
            f"[{ret_style}]{result['total_return_pct']:.2f}%[/{ret_style}]",
            f"[{sh_style}]{result['avg_sharpe']:.3f}[/{sh_style}]",
            f"[red]{result['avg_max_drawdown']:.2f}%[/red]",
            str(result["total_trades"]),
        )

    console.print(table)

    # Benchmark comparison section
    benchmarks = report.get("benchmarks", {})
    if benchmarks:
        console.print()
        console.print(Rule("[bold]Benchmark Comparison[/bold]"))

        bench_table = Table(title="Benchmark vs Strategy Comparison")
        bench_table.add_column("Strategy", style="bold")
        bench_table.add_column("Return %", justify="right")
        bench_table.add_column("Sharpe", justify="right")
        bench_table.add_column("Max DD %", justify="right")

        for _key, bm in benchmarks.items():
            ret_style = "green" if bm["return_pct"] >= 0 else "red"
            sh_style = "green" if bm["sharpe_ratio"] >= 0 else "red"
            bench_table.add_row(
                bm["name"],
                f"[{ret_style}]{bm['return_pct']:.2f}%[/{ret_style}]",
                f"[{sh_style}]{bm['sharpe_ratio']:.3f}[/{sh_style}]",
                f"[red]{bm['max_drawdown']:.2f}%[/red]",
            )

        # Add best risk level for comparison
        rl_results = report.get("risk_level_results", {})
        if rl_results:
            best_level = max(
                rl_results.items(),
                key=lambda x: x[1].get("total_return_pct", 0),
            )
            best_name = best_level[0]
            best = best_level[1]
            # Use portfolio metrics if available
            pm = best.get("portfolio_metrics")
            if pm:
                ret = pm["total_return_pct"]
                sharpe = pm["sharpe_ratio"]
                dd = pm["max_drawdown"]
            else:
                ret = best["total_return_pct"]
                sharpe = best["avg_sharpe"]
                dd = best["avg_max_drawdown"]
            ret_style = "green" if ret >= 0 else "red"
            sh_style = "green" if sharpe >= 0 else "red"
            bench_table.add_row(
                f"Best ({best_name})",
                f"[{ret_style}]{ret:.2f}%[/{ret_style}]",
                f"[{sh_style}]{sharpe:.3f}[/{sh_style}]",
                f"[red]{dd:.2f}%[/red]",
            )

        console.print(bench_table)

        # Benchmark equity curve overlay chart
        if charts_mode != "none":
            try:
                bench_series: dict[str, list[float]] = {}
                for _key, bm in benchmarks.items():
                    curve = bm.get("equity_curve", [])
                    if len(curve) >= 2:
                        bench_series[bm["name"]] = curve

                # Add best risk level equity curve
                if rl_results:
                    best = max(
                        rl_results.values(),
                        key=lambda x: x.get("total_return_pct", 0),
                    )
                    pm = best.get("portfolio_metrics")
                    if pm and len(pm.get("equity_curve", [])) >= 2:
                        bench_series["Best Strategy"] = pm["equity_curve"]

                if bench_series:
                    chart = plotext_multi_line(
                        bench_series,
                        title="Benchmark vs Strategy Equity Curves",
                    )
                    console.print()
                    console.print(Panel(Text.from_ansi(chart), expand=False))
            except Exception:
                pass  # chart rendering is best-effort

    # Per-stock details for each risk level
    if charts_mode != "none":
        console.print()
        console.print(Rule("[bold]Per-Stock Details[/bold]"))

    for level_name, result in report.get("risk_level_results", {}).items():
        # Per-stock table (skip in none mode -- too verbose with 16 stocks x 4 levels)
        if charts_mode != "none" and result.get("stock_results"):
            stock_table = Table(title=f"\n{level_name.upper()} — Per-Stock Results")
            stock_table.add_column("Symbol", style="bold")
            stock_table.add_column("Return %", justify="right")
            stock_table.add_column("Sharpe", justify="right")
            stock_table.add_column("Max DD %", justify="right")
            stock_table.add_column("Win Rate", justify="right")
            stock_table.add_column("Trades", justify="right")

            for sr in result["stock_results"]:
                ret_style = "green" if sr["return_pct"] >= 0 else "red"
                sh_style = "green" if sr["sharpe_ratio"] >= 0 else "red"
                stock_table.add_row(
                    sr["symbol"],
                    f"[{ret_style}]{sr['return_pct']:.2f}%[/{ret_style}]",
                    f"[{sh_style}]{sr['sharpe_ratio']:.3f}[/{sh_style}]",
                    f"[red]{sr['max_drawdown']:.2f}%[/red]",
                    f"{sr['win_rate']:.1%}",
                    str(sr["total_trades"]),
                )

            console.print(stock_table)

        # --- Portfolio Equity Curve chart ---
        pm = result.get("portfolio_metrics")
        if pm and charts_mode not in ("none", "summary"):
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
            fv_style = "green" if pm["final_value"] >= pm["initial_balance"] else "red"
            metrics_table.add_row(
                "Final Value",
                f"[{fv_style}]${pm['final_value']:,.2f}[/{fv_style}]",
            )
            metrics_table.add_row("Total Return", format_pct(pm["total_return_pct"]))
            metrics_table.add_row("Max Drawdown", f"[red]{pm['max_drawdown']:.2f}%[/red]")
            sh_style = "green" if pm["sharpe_ratio"] >= 0 else "red"
            metrics_table.add_row(
                "Sharpe Ratio",
                f"[{sh_style}]{pm['sharpe_ratio']:.3f}[/{sh_style}]",
            )
            so_style = "green" if pm["sortino_ratio"] >= 0 else "red"
            metrics_table.add_row(
                "Sortino Ratio",
                f"[{so_style}]{pm['sortino_ratio']:.3f}[/{so_style}]",
            )
            ca_style = "green" if pm["calmar_ratio"] >= 0 else "red"
            metrics_table.add_row(
                "Calmar Ratio",
                f"[{ca_style}]{pm['calmar_ratio']:.3f}[/{ca_style}]",
            )
            metrics_table.add_row("Total Trades", str(pm["total_trades"]))
            console.print(metrics_table)

        # --- Allocation display ---
        config = report.get("config", {})
        if config.get("portfolio_mode"):
            alloc = config.get("allocation", {})
            weights_dict = alloc.get("weights", {})
            mode = alloc.get("mode", "equal_weight")

            alloc_table = Table(title=f"{level_name.upper()} — Allocation")
            alloc_table.add_column("Symbol", style="bold")
            alloc_table.add_column("Weight %", justify="right")

            if mode == "equal_weight" and result.get("stock_results"):
                n = len(result["stock_results"])
                for sr in result["stock_results"]:
                    alloc_table.add_row(sr["symbol"], f"{100 / n:.1f}%")
            elif weights_dict:
                for sym, w in weights_dict.items():
                    alloc_table.add_row(sym, f"{w * 100:.1f}%")

            if alloc_table.row_count:
                console.print(alloc_table)

        # --- Portfolio Monte Carlo projection summary ---
        pmc = result.get("portfolio_monte_carlo")
        if pmc:
            pmc_table = Table(title=f"{level_name.upper()} — Portfolio Monte Carlo Projection")
            pmc_table.add_column("Metric", style="bold")
            pmc_table.add_column("Value", justify="right")
            pmc_table.add_row("Median Final", f"${pmc['median_final']:,.2f}")
            pmc_table.add_row("P5 Final", f"${pmc['p5_final']:,.2f}")
            pmc_table.add_row("P95 Final", f"${pmc['p95_final']:,.2f}")
            mr_style = "green" if pmc["median_return_pct"] >= 0 else "red"
            pmc_table.add_row(
                "Median Return %",
                f"[{mr_style}]{pmc['median_return_pct']:.2f}%[/{mr_style}]",
            )
            pmc_table.add_row("Worst DD (P95)", f"[red]{pmc['worst_drawdown_p95']:.2f}%[/red]")
            console.print(pmc_table)

        # --- Correlation matrix (skip in none mode -- 16x16 is very wide) ---
        if charts_mode != "none" and pmc and pmc.get("correlation_matrix"):
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

    # Per-stock Monte Carlo projections (skip in none mode)
    if charts_mode != "none":
        console.print()
        console.print(Rule("[bold]Monte Carlo Projections[/bold]"))
        for level_name, result in report.get("risk_level_results", {}).items():
            if not result.get("monte_carlo_projections"):
                continue

            test_d = report["config"]["test_days"]
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
                mr_style = "green" if mc["median_return_pct"] >= 0 else "red"
                mc_table.add_row(
                    mc["symbol"],
                    f"${mc['median_final']:,.2f}",
                    f"${mc['p5_final']:,.2f}",
                    f"${mc['p95_final']:,.2f}",
                    f"[{mr_style}]{mc['median_return_pct']:.2f}%[/{mr_style}]",
                    f"[red]{mc['worst_drawdown_p95']:.2f}%[/red]",
                )

            console.print(mc_table)

    if charts_mode != "none":
        console.print()
        console.print(Rule("[bold]Charts[/bold]"))

        # --- Charts: Equity curve per stock (only in full mode) ---
        if charts_mode == "full":
            total_stock_charts = sum(
                len(rl.get("stock_results") or [])
                for rl in report.get("risk_level_results", {}).values()
            )
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as chart_progress:
                chart_task = chart_progress.add_task(
                    "Rendering charts",
                    total=total_stock_charts,
                )
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
                            chart_progress.update(
                                chart_task,
                                advance=1,
                                description=f"Rendering charts: {sr['symbol']}",
                            )
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
                    console.print(Panel(Text.from_ansi(chart), expand=False))
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


def _print_rebalance_comparison(reports: dict[str, dict]) -> None:
    """Print a side-by-side comparison table of the best risk level across rebalance modes."""
    console.print(Rule("[bold]Rebalance Comparison[/bold]"))

    table = Table(title="Rebalance Comparison")
    table.add_column("Metric", style="bold")
    for mode in reports:
        table.add_column(mode, justify="right")

    rows: dict[str, list[str]] = {
        "Best Return %": [],
        "Best Sharpe": [],
        "Best Max DD %": [],
        "Optimal Risk": [],
    }

    for _mode, report in reports.items():
        rl_results = report.get("risk_level_results", {})
        rec = report.get("recommendation", {})
        optimal = rec.get("optimal_risk_level", "")
        best = rl_results.get(optimal, {})

        pm = best.get("portfolio_metrics")
        if pm:
            ret = pm.get("total_return_pct", 0.0)
            sharpe = pm.get("sharpe_ratio", 0.0)
            dd = pm.get("max_drawdown", 0.0)
        else:
            ret = best.get("total_return_pct", 0.0)
            sharpe = best.get("avg_sharpe", 0.0)
            dd = best.get("avg_max_drawdown", 0.0)

        ret_s = "green" if ret >= 0 else "red"
        sh_s = "green" if sharpe >= 0 else "red"
        rows["Best Return %"].append(f"[{ret_s}]{ret:.2f}%[/{ret_s}]")
        rows["Best Sharpe"].append(f"[{sh_s}]{sharpe:.3f}[/{sh_s}]")
        rows["Best Max DD %"].append(f"[red]{dd:.2f}%[/red]")
        rows["Optimal Risk"].append(optimal)

    for metric, values in rows.items():
        table.add_row(metric, *values)

    console.print(table)
