"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { runSimulation, getSimulationRuns } from "@/lib/api";
import ChartContainer from "@/components/shared/ChartContainer";
import DataTable from "@/components/shared/DataTable";
import { formatCurrency, formatPercent, formatNumber, cn } from "@/lib/formatters";
import { themeColors, chartAxisTick, chartGridProps, chartTooltipStyle } from "@/lib/chartTheme";
import { Activity, Play, AlertTriangle, Target, Zap, Shield, Award } from "lucide-react";

const ALL_STOCKS = [
  "SPY", "QQQ", "DIA", "IWM",
  "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
  "XLF", "XLK", "XLE", "XLV", "XLI",
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

type RiskResult = {
  risk_level: string;
  total_return_pct: number;
  avg_sharpe: number;
  avg_max_drawdown: number;
  total_trades: number;
  stock_results: StockResult[];
  monte_carlo_projections: MCProjection[];
};

type SimReport = {
  id: string;
  status: string;
  config: Record<string, unknown>;
  risk_level_results: Record<string, RiskResult>;
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
  });

  const [report, setReport] = useState<SimReport | null>(null);
  const [activeRisk, setActiveRisk] = useState("moderate");

  const mutation = useMutation({
    mutationFn: () => runSimulation(config),
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
              <label className="mb-1 block text-xs text-muted">Initial Balance ($)</label>
              <input
                type="number"
                value={config.initial_balance}
                onChange={(e) => setConfig({ ...config, initial_balance: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Training Days</label>
              <input
                type="number"
                value={config.train_days}
                onChange={(e) => setConfig({ ...config, train_days: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Test Days</label>
              <input
                type="number"
                value={config.test_days}
                onChange={(e) => setConfig({ ...config, test_days: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">MC Simulations</label>
              <input
                type="number"
                value={config.mc_simulations}
                onChange={(e) => setConfig({ ...config, mc_simulations: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Stocks (comma-separated)</label>
              <textarea
                value={config.stocks.join(", ")}
                onChange={(e) =>
                  setConfig({ ...config, stocks: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })
                }
                rows={3}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Risk Levels</label>
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
            <button
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
                        Recommended: <span className="text-accent">{report.recommendation.optimal_risk_level.replace("_", " ")}</span>
                        <span className="ml-2 text-xs text-muted">({formatPercent(report.recommendation.confidence * 100, 0)} confidence)</span>
                      </p>
                      <p className="mt-1 text-xs text-muted">{report.recommendation.reasoning}</p>
                      {Object.keys(report.recommendation.suggested_weights).length > 0 && (
                        <p className="mt-1 text-xs text-muted">
                          Strategy weights: {Object.entries(report.recommendation.suggested_weights).map(([k, v]) => `${k}: ${(v * 100).toFixed(0)}%`).join(", ")}
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
                      key={level}
                      onClick={() => setActiveRisk(level)}
                      className={cn(
                        "rounded-xl border p-4 text-left transition-all",
                        isActive ? "border-accent bg-accent/10" : "border-border bg-card hover:bg-card-hover",
                        isRecommended && "ring-1 ring-accent/50"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <Icon size={16} className="text-muted" />
                        {isRecommended && <span className="text-[10px] font-medium text-accent">BEST</span>}
                      </div>
                      <p className="mt-2 text-xs text-muted">{level.replace("_", " ")}</p>
                      <p className={cn("text-lg font-semibold", r.total_return_pct >= 0 ? "text-profit" : "text-loss")}>
                        {r.total_return_pct >= 0 ? "+" : ""}{r.total_return_pct.toFixed(2)}%
                      </p>
                      <p className="text-[10px] text-muted">Sharpe {r.avg_sharpe.toFixed(2)} | DD {r.avg_max_drawdown.toFixed(1)}%</p>
                    </button>
                  );
                })}
              </div>

              {/* Comparison Chart */}
              <ChartContainer title="Risk Level Comparison" subtitle="Return % across all risk profiles">
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={comparisonData}>
                    <CartesianGrid {...chartGridProps} />
                    <XAxis dataKey="name" tick={chartAxisTick} />
                    <YAxis tick={chartAxisTick} tickFormatter={(v) => `${v}%`} />
                    <Tooltip contentStyle={chartTooltipStyle} />
                    <Legend />
                    <Bar dataKey="return" name="Avg Return %" fill={themeColors.green} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="drawdown" name="Avg Max DD %" fill={themeColors.red} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>

              {/* Per-Stock Table for Active Risk Level */}
              {activeResult && activeResult.stock_results.length > 0 && (
                <ChartContainer title={`${activeRisk.replace("_", " ").toUpperCase()} \u2014 Per-Stock Results`} subtitle={`${activeResult.total_trades} total trades`}>
                  <DataTable
                    columns={[
                      { key: "symbol", header: "Symbol" },
                      {
                        key: "return_pct",
                        header: "Return %",
                        render: (r) => (
                          <span className={cn((r.return_pct as number) >= 0 ? "text-profit" : "text-loss")}>
                            {(r.return_pct as number) >= 0 ? "+" : ""}{formatPercent(r.return_pct as number)}
                          </span>
                        ),
                      },
                      { key: "sharpe_ratio", header: "Sharpe", render: (r) => formatNumber(r.sharpe_ratio as number) },
                      { key: "max_drawdown", header: "Max DD %", render: (r) => formatPercent(r.max_drawdown as number) },
                      { key: "win_rate", header: "Win Rate", render: (r) => formatPercent((r.win_rate as number) * 100, 0) },
                      { key: "total_trades", header: "Trades" },
                      {
                        key: "total_pnl",
                        header: "P&L",
                        render: (r) => (
                          <span className={cn((r.total_pnl as number) >= 0 ? "text-profit" : "text-loss")}>
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
                <ChartContainer title={`${activeRisk.replace("_", " ").toUpperCase()} \u2014 Monte Carlo Projections`} subtitle={`${activeResult.monte_carlo_projections[0]?.n_paths || 0} simulated paths per stock`}>
                  <DataTable
                    columns={[
                      { key: "symbol", header: "Symbol" },
                      { key: "median_final", header: "Median $", render: (r) => formatCurrency(r.median_final as number) },
                      { key: "p5_final", header: "P5 $", render: (r) => formatCurrency(r.p5_final as number) },
                      { key: "p95_final", header: "P95 $", render: (r) => formatCurrency(r.p95_final as number) },
                      {
                        key: "median_return_pct",
                        header: "Median Ret %",
                        render: (r) => (
                          <span className={cn((r.median_return_pct as number) >= 0 ? "text-profit" : "text-loss")}>
                            {formatPercent(r.median_return_pct as number)}
                          </span>
                        ),
                      },
                      { key: "worst_drawdown_p95", header: "Worst DD (P95)", render: (r) => formatPercent(r.worst_drawdown_p95 as number) },
                    ]}
                    data={activeResult.monte_carlo_projections as unknown as Record<string, unknown>[]}
                    emptyMessage="No projections"
                  />
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
                Fetches real stock data, runs walk-forward backtests across risk levels, and generates Monte Carlo projections with strategy recommendations.
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
                    r.status === "completed" ? "bg-profit/20 text-profit" : r.status === "failed" ? "bg-loss/20 text-loss" : "bg-warning/20 text-warning"
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
