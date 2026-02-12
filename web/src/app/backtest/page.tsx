"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { runBacktest, getBacktestRuns } from "@/lib/api";
import ChartContainer from "@/components/shared/ChartContainer";
import StatCard from "@/components/shared/StatCard";
import DataTable from "@/components/shared/DataTable";
import { formatCurrency, formatPercent, formatNumber, cn } from "@/lib/formatters";
import { themeColors, chartAxisTick, chartGridProps, chartTooltipStyle } from "@/lib/chartTheme";
import { FlaskConical, Play, TrendingUp, BarChart3, AlertTriangle, Target } from "lucide-react";

export default function BacktestPage() {
  const queryClient = useQueryClient();
  const { data: runs } = useQuery({ queryKey: ["backtest-runs"], queryFn: getBacktestRuns });

  const [config, setConfig] = useState({
    start_date: "2024-01-01",
    end_date: "2024-12-31",
    strategies: [] as string[],
    symbols: ["BTC/USD"],
    initial_capital: 100000,
  });

  const [selectedRun, setSelectedRun] = useState<Record<string, unknown> | null>(null);

  const mutation = useMutation({
    mutationFn: () => runBacktest(config),
    onSuccess: (data) => {
      setSelectedRun(data as Record<string, unknown>);
      queryClient.invalidateQueries({ queryKey: ["backtest-runs"] });
    },
  });

  const result = (selectedRun?.result || null) as Record<string, unknown> | null;
  const equityCurve = (result?.equity_curve || []) as { index: number; value: number }[];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Backtesting</h1>

      <div className="grid grid-cols-3 gap-6">
        {/* Config form */}
        <ChartContainer title="Backtest Configuration" className="col-span-1">
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-muted">Start Date</label>
              <input
                type="date"
                value={config.start_date}
                onChange={(e) => setConfig({ ...config, start_date: e.target.value })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">End Date</label>
              <input
                type="date"
                value={config.end_date}
                onChange={(e) => setConfig({ ...config, end_date: e.target.value })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Initial Capital</label>
              <input
                type="number"
                value={config.initial_capital}
                onChange={(e) => setConfig({ ...config, initial_capital: Number(e.target.value) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-muted">Symbols (comma-separated)</label>
              <input
                type="text"
                value={config.symbols.join(", ")}
                onChange={(e) => setConfig({ ...config, symbols: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
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
              {mutation.isPending ? "Running..." : "Run Backtest"}
            </button>
          </div>
        </ChartContainer>

        {/* Results */}
        <div className="col-span-2 space-y-4">
          {result && !result.error ? (
            <>
              <div className="grid grid-cols-4 gap-3">
                <StatCard title="Return" value={formatPercent(result.return_pct as number)} icon={TrendingUp} trend={(result.return_pct as number) >= 0 ? "up" : "down"} />
                <StatCard title="Win Rate" value={formatPercent((result.win_rate as number) * 100, 0)} icon={Target} />
                <StatCard title="Max Drawdown" value={formatPercent(result.max_drawdown as number)} icon={AlertTriangle} trend="down" />
                <StatCard title="Sharpe Ratio" value={formatNumber(result.sharpe_ratio as number)} icon={BarChart3} />
              </div>
              <ChartContainer title="Equity Curve" subtitle={`${result.total_trades} trades`}>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={equityCurve}>
                    <CartesianGrid {...chartGridProps} />
                    <XAxis dataKey="index" tick={chartAxisTick} />
                    <YAxis tick={chartAxisTick} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                    <Tooltip contentStyle={chartTooltipStyle} formatter={(v) => [formatCurrency(Number(v ?? 0)), "Equity"]} />
                    <defs>
                      <linearGradient id="btEq" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={themeColors.green} stopOpacity={0.4} />
                        <stop offset="100%" stopColor={themeColors.green} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="value" stroke={themeColors.green} fill="url(#btEq)" />
                  </AreaChart>
                </ResponsiveContainer>
              </ChartContainer>
            </>
          ) : result?.error ? (
            <div className="rounded-xl border border-border bg-card p-8 text-center text-muted">
              <FlaskConical size={32} className="mx-auto mb-3 text-warning" />
              <p className="text-sm">{result.error as string}</p>
            </div>
          ) : (
            <div className="rounded-xl border border-border bg-card p-8 text-center text-muted">
              <FlaskConical size={32} className="mx-auto mb-3" />
              <p className="text-sm">Configure and run a backtest to see results</p>
            </div>
          )}
        </div>
      </div>

      {/* Previous runs */}
      <ChartContainer title="Previous Runs">
        <DataTable
          columns={[
            { key: "id", header: "Run ID" },
            { key: "status", header: "Status", render: (r) => (
              <span className={cn(
                "rounded-full px-2 py-0.5 text-xs",
                r.status === "completed" ? "bg-profit/20 text-profit" :
                r.status === "failed" ? "bg-loss/20 text-loss" : "bg-warning/20 text-warning"
              )}>{r.status as string}</span>
            )},
            { key: "started_at", header: "Started" },
            { key: "config", header: "Symbols", render: (r) => {
              const c = r.config as Record<string, unknown>;
              return (c?.symbols as string[])?.join(", ") || "";
            }},
          ]}
          data={(runs || []) as Record<string, unknown>[]}
          emptyMessage="No backtest runs yet"
        />
      </ChartContainer>
    </div>
  );
}
