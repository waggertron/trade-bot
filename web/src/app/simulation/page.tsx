"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, Award, Play, Shield, Target, Zap } from "lucide-react";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ChartContainer from "@/components/shared/ChartContainer";
import DataTable from "@/components/shared/DataTable";
import { getSimulationRuns, runSimulation } from "@/lib/api";
import { chartAxisTick, chartGridProps, chartTooltipStyle, themeColors } from "@/lib/chartTheme";
import { cn, formatCurrency, formatNumber, formatPercent } from "@/lib/formatters";

const ALL_STOCKS = [
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
];

const RISK_LEVELS = ["conservative", "moderate", "aggressive", "very_aggressive"];

const RISK_ICONS: Record<string, typeof Shield> = {
  conservative: Shield,
  moderate: Target,
  aggressive: Zap,
  very_aggressive: AlertTriangle,
};

type StockResult = {
  symbol: string;
  return_pct: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  initial_balance: number;
  final_value: number;
  total_pnl: number;
};

type MCProjection = {
  symbol: string;
  median_final: number;
  p5_final: number;
  p95_final: number;
  median_return_pct: number;
  p5_return_pct: number;
  p95_return_pct: number;
  worst_drawdown_p95: number;
  n_paths: number;
};

type PortfolioMetricsType = {
  initial_balance: number;
  final_value: number;
  total_return_pct: number;
  max_drawdown: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  total_trades: number;
  equity_curve: number[];
  daily_returns: number[];
  rebalance_dates: number[];
};

type PortfolioMCType = {
  median_final: number;
  p5_final: number;
  p95_final: number;
  median_return_pct: number;
  p5_return_pct: number;
  p95_return_pct: number;
  worst_drawdown_p95: number;
  n_paths: number;
  correlation_matrix: number[][];
};

type RiskResult = {
  risk_level: string;
  total_return_pct: number;
  avg_sharpe: number;
  avg_max_drawdown: number;
  total_trades: number;
  stock_results: StockResult[];
  monte_carlo_projections: MCProjection[];
  portfolio_metrics?: PortfolioMetricsType | null;
  portfolio_monte_carlo?: PortfolioMCType | null;
};

type BenchmarkResultType = {
  name: string;
  initial_balance: number;
  final_value: number;
  return_pct: number;
  max_drawdown: number;
  sharpe_ratio: number;
  equity_curve: number[];
};

type SimReport = {
  id: string;
  status: string;
  config: Record<string, unknown>;
  risk_level_results: Record<string, RiskResult>;
  benchmarks?: Record<string, BenchmarkResultType>;
  recommendation: {
    optimal_risk_level: string;
    reasoning: string;
    suggested_weights: Record<string, number>;
    confidence: number;
  } | null;
  started_at: string;
  completed_at: string;
  error: string | null;
};

export default function SimulationPage() {
  const queryClient = useQueryClient();
  const { data: runs } = useQuery({ queryKey: ["simulation-runs"], queryFn: getSimulationRuns });

  const [config, setConfig] = useState({
    stocks: ALL_STOCKS,
    initial_balance: 10000,
    train_days: 60,
    test_days: 30,
    risk_levels: RISK_LEVELS,
    mc_simulations: 1000,
    portfolio_mode: false,
    allocation_mode: "equal_weight" as string,
    custom_weights: {} as Record<string, number>,
    rebalance_frequency: "none" as string,
    rebalance_threshold_pct: 5.0,
    mc_seed: null as number | null,
    max_position_pct: null as number | null,
  });

  const [report, setReport] = useState<SimReport | null>(null);
  const [activeRisk, setActiveRisk] = useState("moderate");

  const mutation = useMutation({
    mutationFn: () =>
      runSimulation({
        ...config,
        ...(config.mc_seed != null ? { mc_seed: config.mc_seed } : {}),
        ...(config.max_position_pct != null ? { max_position_pct: config.max_position_pct } : {}),
        ...(config.portfolio_mode
          ? {
              portfolio_mode: true,
              allocation_mode: config.allocation_mode,
              custom_weights:
                config.allocation_mode === "custom" ? config.custom_weights : undefined,
              rebalance_frequency: config.rebalance_frequency,
              rebalance_threshold_pct: config.rebalance_threshold_pct,
            }
          : {}),
      }),
    onSuccess: (data) => {
      setReport(data as unknown as SimReport);
      queryClient.invalidateQueries({ queryKey: ["simulation-runs"] });
    },
  });

  const activeResult = report?.risk_level_results?.[activeRisk];

  const comparisonData = report
    ? Object.entries(report.risk_level_results).map(([level, r]) => ({
        name: level.replace("_", " "),
        return: r.total_return_pct,
        sharpe: r.avg_sharpe,
        drawdown: r.avg_max_drawdown,
        trades: r.total_trades,
      }))
    : [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold flex items-center gap-2">
        <Activity size={22} /> Simulation
      </h1>

      <div className="grid grid-cols-4 gap-6">
        {/* Config Panel */}
        <ChartContainer title="Configuration" className="col-span-1">
          <div className="space-y-4">
            <div>
              <label htmlFor="sim-initial-balance" className="mb-1 block text-xs text-muted">
                Initial Balance ($)
              </label>
              <input
                id="sim-initial-balance"
                type="number"
                value={config.initial_balance}
                onChange={(e) => setConfig({ ...config, initial_balance: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label htmlFor="sim-train-days" className="mb-1 block text-xs text-muted">
                Training Days
              </label>
              <input
                id="sim-train-days"
                type="number"
                value={config.train_days}
                onChange={(e) => setConfig({ ...config, train_days: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label htmlFor="sim-test-days" className="mb-1 block text-xs text-muted">
                Test Days
              </label>
              <input
                id="sim-test-days"
                type="number"
                value={config.test_days}
                onChange={(e) => setConfig({ ...config, test_days: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label htmlFor="sim-mc-count" className="mb-1 block text-xs text-muted">
                MC Simulations
              </label>
              <input
                id="sim-mc-count"
                type="number"
                value={config.mc_simulations}
                onChange={(e) => setConfig({ ...config, mc_simulations: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label htmlFor="sim-mc-seed" className="mb-1 block text-xs text-muted">
                Random Seed (optional)
              </label>
              <input
                id="sim-mc-seed"
                type="number"
                value={config.mc_seed ?? ""}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    mc_seed: e.target.value === "" ? null : Number(e.target.value),
                  })
                }
                placeholder="Leave empty for random"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label htmlFor="sim-max-position-pct" className="mb-1 block text-xs text-muted">
                Max Position Size (%) <span className="text-muted/60">optional</span>
              </label>
              <input
                id="sim-max-position-pct"
                type="number"
                min={0.1}
                max={100}
                step={0.1}
                value={config.max_position_pct ?? ""}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    max_position_pct: e.target.value === "" ? null : Number(e.target.value),
                  })
                }
                placeholder="Per risk level default"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label htmlFor="sim-stocks" className="mb-1 block text-xs text-muted">
                Stocks (comma-separated)
              </label>
              <textarea
                id="sim-stocks"
                value={config.stocks.join(", ")}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    stocks: e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
                rows={3}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground"
              />
            </div>
            <div>
              <span className="mb-1 block text-xs text-muted">Risk Levels</span>
              <div className="space-y-1">
                {RISK_LEVELS.map((level) => (
                  <label key={level} className="flex items-center gap-2 text-xs text-foreground">
                    <input
                      type="checkbox"
                      checked={config.risk_levels.includes(level)}
                      onChange={(e) => {
                        const newLevels = e.target.checked
                          ? [...config.risk_levels, level]
                          : config.risk_levels.filter((l) => l !== level);
                        setConfig({ ...config, risk_levels: newLevels });
                      }}
                      className="rounded border-border"
                    />
                    {level.replace("_", " ")}
                  </label>
                ))}
              </div>
            </div>

            {/* Portfolio Mode Toggle */}
            <div className="border-t border-border pt-4 mt-4">
              <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={config.portfolio_mode}
                  onChange={(e) => setConfig({ ...config, portfolio_mode: e.target.checked })}
                  className="rounded border-border"
                />
                Portfolio Mode
              </label>

              {config.portfolio_mode && (
                <div className="mt-3 space-y-3">
                  {/* Allocation selector */}
                  <div>
                    <label className="mb-1 block text-xs text-muted">Allocation</label>
                    <select
                      value={config.allocation_mode}
                      onChange={(e) =>
                        setConfig({ ...config, allocation_mode: e.target.value })
                      }
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
                    >
                      <option value="equal_weight">Equal Weight</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>

                  {/* Custom weight inputs per stock */}
                  {config.allocation_mode === "custom" && (
                    <div className="space-y-2">
                      <span className="text-xs text-muted">
                        Stock Weights (must sum to 100%)
                      </span>
                      {config.stocks.map((stock) => (
                        <div key={stock} className="flex items-center gap-2">
                          <span className="w-12 text-xs text-foreground">{stock}</span>
                          <input
                            type="range"
                            min="0"
                            max="100"
                            value={(config.custom_weights[stock] || 0) * 100}
                            onChange={(e) => {
                              const newWeights = {
                                ...config.custom_weights,
                                [stock]: Number(e.target.value) / 100,
                              };
                              setConfig({ ...config, custom_weights: newWeights });
                            }}
                            className="flex-1"
                          />
                          <span className="w-10 text-xs text-muted text-right">
                            {((config.custom_weights[stock] || 0) * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                      <p className="text-[10px] text-muted">
                        Total:{" "}
                        {(
                          Object.values(config.custom_weights).reduce((a, b) => a + b, 0) * 100
                        ).toFixed(0)}
                        %
                      </p>
                    </div>
                  )}

                  {/* Rebalance frequency */}
                  <div>
                    <label className="mb-1 block text-xs text-muted">Rebalance Frequency</label>
                    <select
                      value={config.rebalance_frequency}
                      onChange={(e) =>
                        setConfig({ ...config, rebalance_frequency: e.target.value })
                      }
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
                    >
                      <option value="none">None</option>
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option>
                      <option value="monthly">Monthly</option>
                    </select>
                  </div>

                  {/* Rebalance threshold */}
                  <div>
                    <label
                      htmlFor="sim-rebalance-threshold"
                      className="mb-1 block text-xs text-muted"
                    >
                      Rebalance Threshold (%)
                    </label>
                    <input
                      id="sim-rebalance-threshold"
                      type="number"
                      min={0}
                      max={100}
                      step={0.5}
                      value={config.rebalance_threshold_pct}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          rebalance_threshold_pct: Number(e.target.value),
                        })
                      }
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
                    />
                  </div>
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {mutation.isPending ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <Play size={14} />
              )}
              {mutation.isPending ? "Running Simulation..." : "Run Simulation"}
            </button>
          </div>
        </ChartContainer>

        {/* Results Area */}
        <div className="col-span-3 space-y-4">
          {report && !report.error ? (
            <>
              {/* Recommendation Banner */}
              {report.recommendation && (
                <div className="rounded-xl border border-accent/30 bg-accent/5 p-4">
                  <div className="flex items-start gap-3">
                    <Award size={20} className="mt-0.5 text-accent" />
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        Recommended:{" "}
                        <span className="text-accent">
                          {report.recommendation.optimal_risk_level.replace("_", " ")}
                        </span>
                        <span className="ml-2 text-xs text-muted">
                          ({formatPercent(report.recommendation.confidence * 100, 0)} confidence)
                        </span>
                      </p>
                      <p className="mt-1 text-xs text-muted">{report.recommendation.reasoning}</p>
                      {Object.keys(report.recommendation.suggested_weights).length > 0 && (
                        <p className="mt-1 text-xs text-muted">
                          Strategy weights:{" "}
                          {Object.entries(report.recommendation.suggested_weights)
                            .map(([k, v]) => `${k}: ${(v * 100).toFixed(0)}%`)
                            .join(", ")}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Risk Level Overview Cards */}
              <div className="grid grid-cols-4 gap-3">
                {Object.entries(report.risk_level_results).map(([level, r]) => {
                  const Icon = RISK_ICONS[level] || Target;
                  const isActive = level === activeRisk;
                  const isRecommended = level === report.recommendation?.optimal_risk_level;
                  return (
                    <button
                      type="button"
                      key={level}
                      onClick={() => setActiveRisk(level)}
                      className={cn(
                        "rounded-xl border p-4 text-left transition-all",
                        isActive
                          ? "border-accent bg-accent/10"
                          : "border-border bg-card hover:bg-card-hover",
                        isRecommended && "ring-1 ring-accent/50",
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <Icon size={16} className="text-muted" />
                        {isRecommended && (
                          <span className="text-[10px] font-medium text-accent">BEST</span>
                        )}
                      </div>
                      <p className="mt-2 text-xs text-muted">{level.replace("_", " ")}</p>
                      <p
                        className={cn(
                          "text-lg font-semibold",
                          r.total_return_pct >= 0 ? "text-profit" : "text-loss",
                        )}
                      >
                        {r.total_return_pct >= 0 ? "+" : ""}
                        {r.total_return_pct.toFixed(2)}%
                      </p>
                      <p className="text-[10px] text-muted">
                        Sharpe {r.avg_sharpe.toFixed(2)} | DD {r.avg_max_drawdown.toFixed(1)}%
                      </p>
                    </button>
                  );
                })}
              </div>

              {/* Benchmark Comparison */}
              {report.benchmarks && Object.keys(report.benchmarks).length > 0 && (
                <ChartContainer
                  title="Benchmark Comparison"
                  subtitle="Strategy performance vs passive SPY benchmarks"
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border text-left text-xs text-muted">
                          <th className="px-4 py-2">Strategy</th>
                          <th className="px-4 py-2 text-right">Return %</th>
                          <th className="px-4 py-2 text-right">Sharpe</th>
                          <th className="px-4 py-2 text-right">Max DD %</th>
                          <th className="px-4 py-2 text-right">Final Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.values(report.benchmarks).map((bm) => (
                          <tr key={bm.name} className="border-b border-border/50">
                            <td className="px-4 py-2 font-medium">{bm.name}</td>
                            <td
                              className={cn(
                                "px-4 py-2 text-right",
                                bm.return_pct >= 0 ? "text-profit" : "text-loss",
                              )}
                            >
                              {bm.return_pct >= 0 ? "+" : ""}
                              {formatPercent(bm.return_pct)}
                            </td>
                            <td className="px-4 py-2 text-right">
                              {formatNumber(bm.sharpe_ratio)}
                            </td>
                            <td className="px-4 py-2 text-right">
                              {formatPercent(bm.max_drawdown)}
                            </td>
                            <td className="px-4 py-2 text-right">
                              {formatCurrency(bm.final_value)}
                            </td>
                          </tr>
                        ))}
                        {/* Best risk level row */}
                        {(() => {
                          const entries = Object.entries(report.risk_level_results);
                          if (entries.length === 0) return null;
                          const [bestLevel, bestResult] = entries.reduce((best, curr) =>
                            curr[1].total_return_pct > best[1].total_return_pct ? curr : best,
                          );
                          const pm = bestResult.portfolio_metrics;
                          const ret = pm ? pm.total_return_pct : bestResult.total_return_pct;
                          const sharpe = pm ? pm.sharpe_ratio : bestResult.avg_sharpe;
                          const dd = pm ? pm.max_drawdown : bestResult.avg_max_drawdown;
                          const finalVal = pm ? pm.final_value : 0;
                          return (
                            <tr className="border-t-2 border-accent/30 font-semibold">
                              <td className="px-4 py-2">
                                Best ({bestLevel.replace("_", " ")})
                              </td>
                              <td
                                className={cn(
                                  "px-4 py-2 text-right",
                                  ret >= 0 ? "text-profit" : "text-loss",
                                )}
                              >
                                {ret >= 0 ? "+" : ""}
                                {formatPercent(ret)}
                              </td>
                              <td className="px-4 py-2 text-right">
                                {formatNumber(sharpe)}
                              </td>
                              <td className="px-4 py-2 text-right">
                                {formatPercent(dd)}
                              </td>
                              <td className="px-4 py-2 text-right">
                                {finalVal > 0 ? formatCurrency(finalVal) : "\u2014"}
                              </td>
                            </tr>
                          );
                        })()}
                      </tbody>
                    </table>
                  </div>

                  {/* Benchmark equity curve overlay */}
                  {(() => {
                    const benchmarks = report.benchmarks!;
                    const curves = Object.values(benchmarks)
                      .filter((bm) => bm.equity_curve.length > 1);
                    if (curves.length === 0) return null;
                    const maxLen = Math.max(...curves.map((c) => c.equity_curve.length));
                    const chartData = Array.from({ length: maxLen }, (_, i) => {
                      const point: Record<string, number> = { day: i };
                      for (const bm of curves) {
                        if (i < bm.equity_curve.length) {
                          point[bm.name] = bm.equity_curve[i];
                        }
                      }
                      return point;
                    });
                    const colors = [themeColors.cyan, themeColors.orange, themeColors.purple];
                    return (
                      <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={chartData}>
                          <CartesianGrid {...chartGridProps} />
                          <XAxis dataKey="day" tick={chartAxisTick} />
                          <YAxis
                            tick={chartAxisTick}
                            tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
                          />
                          <Tooltip
                            contentStyle={chartTooltipStyle}
                            formatter={(v: number | undefined) =>
                              v != null ? [`$${v.toFixed(2)}`, ""] : ["-", ""]
                            }
                          />
                          <Legend />
                          {curves.map((bm, idx) => (
                            <Line
                              key={bm.name}
                              type="monotone"
                              dataKey={bm.name}
                              stroke={colors[idx % colors.length]}
                              dot={false}
                              strokeWidth={2}
                            />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    );
                  })()}
                </ChartContainer>
              )}

              {/* Comparison Chart */}
              <ChartContainer
                title="Risk Level Comparison"
                subtitle="Return % across all risk profiles"
              >
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={comparisonData}>
                    <CartesianGrid {...chartGridProps} />
                    <XAxis dataKey="name" tick={chartAxisTick} />
                    <YAxis tick={chartAxisTick} tickFormatter={(v) => `${v}%`} />
                    <Tooltip contentStyle={chartTooltipStyle} />
                    <Legend />
                    <Bar
                      dataKey="return"
                      name="Avg Return %"
                      fill={themeColors.green}
                      radius={[4, 4, 0, 0]}
                    />
                    <Bar
                      dataKey="drawdown"
                      name="Avg Max DD %"
                      fill={themeColors.red}
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>

              {/* Per-Stock Table for Active Risk Level */}
              {activeResult && activeResult.stock_results.length > 0 && (
                <ChartContainer
                  title={`${activeRisk.replace("_", " ").toUpperCase()} \u2014 Per-Stock Results`}
                  subtitle={`${activeResult.total_trades} total trades`}
                >
                  <DataTable
                    columns={[
                      { key: "symbol", header: "Symbol" },
                      {
                        key: "return_pct",
                        header: "Return %",
                        render: (r) => (
                          <span
                            className={cn(
                              (r.return_pct as number) >= 0 ? "text-profit" : "text-loss",
                            )}
                          >
                            {(r.return_pct as number) >= 0 ? "+" : ""}
                            {formatPercent(r.return_pct as number)}
                          </span>
                        ),
                      },
                      {
                        key: "sharpe_ratio",
                        header: "Sharpe",
                        render: (r) => formatNumber(r.sharpe_ratio as number),
                      },
                      {
                        key: "max_drawdown",
                        header: "Max DD %",
                        render: (r) => formatPercent(r.max_drawdown as number),
                      },
                      {
                        key: "win_rate",
                        header: "Win Rate",
                        render: (r) => formatPercent((r.win_rate as number) * 100, 0),
                      },
                      { key: "total_trades", header: "Trades" },
                      {
                        key: "total_pnl",
                        header: "P&L",
                        render: (r) => (
                          <span
                            className={cn(
                              (r.total_pnl as number) >= 0 ? "text-profit" : "text-loss",
                            )}
                          >
                            {formatCurrency(r.total_pnl as number)}
                          </span>
                        ),
                      },
                    ]}
                    data={activeResult.stock_results as unknown as Record<string, unknown>[]}
                    emptyMessage="No stock results"
                  />
                </ChartContainer>
              )}

              {/* Monte Carlo Projections Table */}
              {activeResult && activeResult.monte_carlo_projections.length > 0 && (
                <ChartContainer
                  title={`${activeRisk.replace("_", " ").toUpperCase()} \u2014 Monte Carlo Projections`}
                  subtitle={`${activeResult.monte_carlo_projections[0]?.n_paths || 0} simulated paths per stock`}
                >
                  <DataTable
                    columns={[
                      { key: "symbol", header: "Symbol" },
                      {
                        key: "median_final",
                        header: "Median $",
                        render: (r) => formatCurrency(r.median_final as number),
                      },
                      {
                        key: "p5_final",
                        header: "P5 $",
                        render: (r) => formatCurrency(r.p5_final as number),
                      },
                      {
                        key: "p95_final",
                        header: "P95 $",
                        render: (r) => formatCurrency(r.p95_final as number),
                      },
                      {
                        key: "median_return_pct",
                        header: "Median Ret %",
                        render: (r) => (
                          <span
                            className={cn(
                              (r.median_return_pct as number) >= 0 ? "text-profit" : "text-loss",
                            )}
                          >
                            {formatPercent(r.median_return_pct as number)}
                          </span>
                        ),
                      },
                      {
                        key: "worst_drawdown_p95",
                        header: "Worst DD (P95)",
                        render: (r) => formatPercent(r.worst_drawdown_p95 as number),
                      },
                    ]}
                    data={
                      activeResult.monte_carlo_projections as unknown as Record<string, unknown>[]
                    }
                    emptyMessage="No projections"
                  />
                </ChartContainer>
              )}

              {/* Portfolio Equity Curve */}
              {activeResult?.portfolio_metrics?.equity_curve &&
                activeResult.portfolio_metrics.equity_curve.length > 1 && (
                  <ChartContainer
                    title={`${activeRisk.replace("_", " ").toUpperCase()} \u2014 Portfolio Equity Curve`}
                    subtitle="Combined portfolio value over time"
                  >
                    <ResponsiveContainer width="100%" height={250}>
                      <LineChart
                        data={activeResult.portfolio_metrics.equity_curve.map((val, i) => ({
                          day: i,
                          value: val,
                        }))}
                      >
                        <CartesianGrid {...chartGridProps} />
                        <XAxis dataKey="day" tick={chartAxisTick} />
                        <YAxis
                          tick={chartAxisTick}
                          tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`}
                        />
                        <Tooltip
                          contentStyle={chartTooltipStyle}
                          formatter={(v: number | undefined) =>
                            v != null ? [`$${v.toFixed(2)}`, "Value"] : ["-", "Value"]
                          }
                        />
                        <Line
                          type="monotone"
                          dataKey="value"
                          stroke={themeColors.accent}
                          dot={false}
                          strokeWidth={2}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </ChartContainer>
                )}

              {/* Portfolio Metrics Card */}
              {activeResult?.portfolio_metrics && (
                <ChartContainer
                  title={`${activeRisk.replace("_", " ").toUpperCase()} \u2014 Portfolio Metrics`}
                  subtitle="Aggregated portfolio performance"
                >
                  <div className="grid grid-cols-4 gap-4 p-4">
                    {[
                      {
                        label: "Total Return",
                        value: `${activeResult.portfolio_metrics.total_return_pct >= 0 ? "+" : ""}${activeResult.portfolio_metrics.total_return_pct.toFixed(2)}%`,
                        color:
                          activeResult.portfolio_metrics.total_return_pct >= 0
                            ? "text-profit"
                            : "text-loss",
                      },
                      {
                        label: "Sharpe Ratio",
                        value: activeResult.portfolio_metrics.sharpe_ratio.toFixed(3),
                        color: "text-foreground",
                      },
                      {
                        label: "Sortino Ratio",
                        value: activeResult.portfolio_metrics.sortino_ratio.toFixed(3),
                        color: "text-foreground",
                      },
                      {
                        label: "Calmar Ratio",
                        value: activeResult.portfolio_metrics.calmar_ratio.toFixed(3),
                        color: "text-foreground",
                      },
                      {
                        label: "Max Drawdown",
                        value: `${activeResult.portfolio_metrics.max_drawdown.toFixed(2)}%`,
                        color: "text-loss",
                      },
                      {
                        label: "Initial Balance",
                        value: formatCurrency(activeResult.portfolio_metrics.initial_balance),
                        color: "text-foreground",
                      },
                      {
                        label: "Final Value",
                        value: formatCurrency(activeResult.portfolio_metrics.final_value),
                        color:
                          activeResult.portfolio_metrics.final_value >=
                          activeResult.portfolio_metrics.initial_balance
                            ? "text-profit"
                            : "text-loss",
                      },
                      {
                        label: "Total Trades",
                        value: String(activeResult.portfolio_metrics.total_trades),
                        color: "text-foreground",
                      },
                    ].map((metric) => (
                      <div key={metric.label} className="text-center">
                        <p className="text-xs text-muted">{metric.label}</p>
                        <p className={cn("text-lg font-semibold", metric.color)}>
                          {metric.value}
                        </p>
                      </div>
                    ))}
                  </div>
                </ChartContainer>
              )}

              {/* Portfolio Monte Carlo Projection */}
              {activeResult?.portfolio_monte_carlo && (
                <ChartContainer
                  title={`${activeRisk.replace("_", " ").toUpperCase()} \u2014 Portfolio Monte Carlo Projection`}
                  subtitle={`${activeResult.portfolio_monte_carlo.n_paths} simulated paths`}
                >
                  <div className="grid grid-cols-3 gap-4 p-4">
                    {[
                      {
                        label: "P5 (Pessimistic)",
                        value: formatCurrency(activeResult.portfolio_monte_carlo.p5_final),
                        sub: `${activeResult.portfolio_monte_carlo.p5_return_pct.toFixed(2)}%`,
                      },
                      {
                        label: "Median",
                        value: formatCurrency(activeResult.portfolio_monte_carlo.median_final),
                        sub: `${activeResult.portfolio_monte_carlo.median_return_pct.toFixed(2)}%`,
                      },
                      {
                        label: "P95 (Optimistic)",
                        value: formatCurrency(activeResult.portfolio_monte_carlo.p95_final),
                        sub: `${activeResult.portfolio_monte_carlo.p95_return_pct.toFixed(2)}%`,
                      },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className="rounded-lg border border-border p-3 text-center"
                      >
                        <p className="text-xs text-muted">{item.label}</p>
                        <p className="text-lg font-semibold text-foreground">{item.value}</p>
                        <p className="text-xs text-muted">{item.sub}</p>
                      </div>
                    ))}
                  </div>
                  <div className="px-4 pb-3">
                    <p className="text-xs text-muted">
                      Worst Drawdown (P95):{" "}
                      {activeResult.portfolio_monte_carlo.worst_drawdown_p95.toFixed(2)}%
                    </p>
                  </div>
                </ChartContainer>
              )}
            </>
          ) : report?.error ? (
            <div className="rounded-xl border border-border bg-card p-8 text-center text-muted">
              <AlertTriangle size={32} className="mx-auto mb-3 text-warning" />
              <p className="text-sm">{report.error}</p>
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-card p-12 text-center text-muted">
              <Activity size={40} className="mx-auto mb-4 opacity-50" />
              <p className="text-sm font-medium">Configure and run a simulation</p>
              <p className="mt-1 text-xs">
                Fetches real stock data, runs walk-forward backtests across risk levels, and
                generates Monte Carlo projections with strategy recommendations.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Previous Runs */}
      <ChartContainer title="Previous Simulation Runs">
        <DataTable
          columns={[
            { key: "id", header: "Run ID" },
            {
              key: "status",
              header: "Status",
              render: (r) => (
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs",
                    r.status === "completed"
                      ? "bg-profit/20 text-profit"
                      : r.status === "failed"
                        ? "bg-loss/20 text-loss"
                        : "bg-warning/20 text-warning",
                  )}
                >
                  {r.status as string}
                </span>
              ),
            },
            { key: "started_at", header: "Started" },
            {
              key: "config",
              header: "Stocks",
              render: (r) => {
                const c = r.config as Record<string, unknown>;
                const stocks = c?.stocks as string[];
                return stocks ? `${stocks.length} stocks` : "";
              },
            },
          ]}
          data={(runs || []) as Record<string, unknown>[]}
          emptyMessage="No simulation runs yet"
        />
      </ChartContainer>
    </div>
  );
}
