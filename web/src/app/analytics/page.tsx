"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";
import { getAttribution, getMonteCarlo, getDrawdown, getCorrelation } from "@/lib/api";
import ChartContainer from "@/components/shared/ChartContainer";
import DataTable from "@/components/shared/DataTable";
import { StatCardSkeleton, ChartSkeleton } from "@/components/shared/LoadingSkeleton";
import StatCard from "@/components/shared/StatCard";
import { formatCurrency, formatPercent, formatNumber, cn } from "@/lib/formatters";
import { themeColors, themeRgba, chartAxisTick, chartGridProps, chartTooltipStyle } from "@/lib/chartTheme";
import { TrendingUp, TrendingDown, BarChart3, Target } from "lucide-react";

export default function AnalyticsPage() {
  const { data: attribution, isLoading: attrLoading } = useQuery({
    queryKey: ["attribution"], queryFn: getAttribution, refetchInterval: 30000,
  });
  const { data: monteCarlo, isLoading: mcLoading } = useQuery({
    queryKey: ["monte-carlo"], queryFn: getMonteCarlo, refetchInterval: 60000,
  });
  const { data: drawdown, isLoading: ddLoading } = useQuery({
    queryKey: ["drawdown"], queryFn: getDrawdown, refetchInterval: 30000,
  });
  const { data: correlation } = useQuery({
    queryKey: ["correlation"], queryFn: getCorrelation, refetchInterval: 60000,
  });

  const attr = attribution as Record<string, unknown> | undefined;
  const mc = monteCarlo as Record<string, unknown> | undefined;
  const strategies = (attr?.strategies || {}) as Record<string, Record<string, unknown>>;

  const strategyRows = Object.values(strategies).map((s) => ({
    name: s.name as string,
    total_trades: s.total_trades as number,
    win_rate: s.win_rate as number,
    total_pnl: s.total_pnl as number,
    avg_win: s.avg_win as number,
    avg_loss: s.avg_loss as number,
    profit_factor: s.profit_factor as number,
    max_consecutive_losses: s.max_consecutive_losses as number,
  }));

  const ddPoints = (drawdown?.points || []) as { index: number; drawdown_pct: number; value: number }[];

  // Profit factor chart data
  const pfData = strategyRows.map((s) => ({
    name: s.name,
    profit_factor: s.profit_factor,
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Analytics</h1>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        {attrLoading ? (
          Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)
        ) : (
          <>
            <StatCard
              title="Total P&L"
              value={formatCurrency(attr?.total_pnl as number || 0)}
              icon={TrendingUp}
              trend={(attr?.total_pnl as number || 0) >= 0 ? "up" : "down"}
            />
            <StatCard
              title="Best Strategy"
              value={(attr?.best_strategy as string) || "N/A"}
              icon={Target}
            />
            <StatCard
              title="Worst Strategy"
              value={(attr?.worst_strategy as string) || "N/A"}
              icon={TrendingDown}
            />
            <StatCard
              title="MC Percentile"
              value={mc ? `${formatNumber(mc.percentile as number)}th` : "N/A"}
              subtitle={mc ? `Actual: ${formatCurrency(mc.actual_final_value as number)}` : undefined}
              icon={BarChart3}
            />
          </>
        )}
      </div>

      {/* Attribution table */}
      <ChartContainer title="Strategy Attribution" subtitle="Performance by strategy">
        <DataTable
          columns={[
            { key: "name", header: "Strategy" },
            { key: "total_trades", header: "Trades", className: "text-right" },
            {
              key: "win_rate", header: "Win Rate", className: "text-right",
              render: (r) => (
                <span className={cn((r.win_rate as number) >= 0.5 ? "text-profit" : "text-loss")}>
                  {formatPercent((r.win_rate as number) * 100, 0)}
                </span>
              ),
            },
            {
              key: "total_pnl", header: "P&L", className: "text-right",
              render: (r) => (
                <span className={cn((r.total_pnl as number) >= 0 ? "text-profit" : "text-loss")}>
                  {formatCurrency(r.total_pnl as number)}
                </span>
              ),
            },
            { key: "avg_win", header: "Avg Win", className: "text-right", render: (r) => formatCurrency(r.avg_win as number) },
            { key: "avg_loss", header: "Avg Loss", className: "text-right", render: (r) => formatCurrency(r.avg_loss as number) },
            {
              key: "profit_factor", header: "Profit Factor", className: "text-right",
              render: (r) => (
                <span className={cn((r.profit_factor as number) >= 1 ? "text-profit" : "text-loss")}>
                  {formatNumber(r.profit_factor as number)}
                </span>
              ),
            },
            { key: "max_consecutive_losses", header: "Max Losing Streak", className: "text-right" },
          ]}
          data={strategyRows}
          emptyMessage="No attribution data yet"
        />
      </ChartContainer>

      <div className="grid grid-cols-2 gap-6">
        {/* Monte Carlo */}
        <ChartContainer title="Monte Carlo Simulation" subtitle={mc ? `${mc.n_simulations} simulations` : ""}>
          {mcLoading ? <ChartSkeleton /> : (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-background p-3">
                  <p className="text-xs text-muted">5th Percentile</p>
                  <p className="text-lg font-medium text-loss">{formatCurrency(mc?.p5_simulated as number || 0)}</p>
                </div>
                <div className="rounded-lg bg-background p-3">
                  <p className="text-xs text-muted">95th Percentile</p>
                  <p className="text-lg font-medium text-profit">{formatCurrency(mc?.p95_simulated as number || 0)}</p>
                </div>
                <div className="rounded-lg bg-background p-3">
                  <p className="text-xs text-muted">Median</p>
                  <p className="text-lg font-medium">{formatCurrency(mc?.median_simulated as number || 0)}</p>
                </div>
                <div className="rounded-lg bg-background p-3">
                  <p className="text-xs text-muted">Actual</p>
                  <p className="text-lg font-medium text-accent">{formatCurrency(mc?.actual_final_value as number || 0)}</p>
                </div>
              </div>
              <div className="rounded-lg bg-background p-3">
                <p className="text-xs text-muted">Worst Drawdown (95th pct)</p>
                <p className="text-lg font-medium text-warning">{formatPercent((mc?.worst_drawdown_p95 as number || 0) * 100)}</p>
              </div>
            </div>
          )}
        </ChartContainer>

        {/* Drawdown chart */}
        <ChartContainer title="Drawdown" subtitle="Peak-to-trough percentage">
          {ddLoading ? <ChartSkeleton /> : (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={ddPoints}>
                <CartesianGrid {...chartGridProps} />
                <XAxis dataKey="index" tick={chartAxisTick} />
                <YAxis tick={chartAxisTick} tickFormatter={(v) => `-${v.toFixed(1)}%`} />
                <Tooltip
                  contentStyle={chartTooltipStyle}
                  formatter={(v) => [`-${Number(v ?? 0).toFixed(2)}%`, "Drawdown"]}
                />
                <defs>
                  <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={themeColors.red} stopOpacity={0.6} />
                    <stop offset="100%" stopColor={themeColors.yellow} stopOpacity={0.1} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="drawdown_pct" stroke={themeColors.red} fill="url(#ddGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </ChartContainer>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Profit factor by strategy */}
        <ChartContainer title="Profit Factor by Strategy" subtitle="Reference line at 1.0">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={pfData} layout="vertical">
              <CartesianGrid {...chartGridProps} />
              <XAxis type="number" tick={chartAxisTick} />
              <YAxis dataKey="name" type="category" tick={chartAxisTick} width={100} />
              <Tooltip
                contentStyle={chartTooltipStyle}
              />
              <ReferenceLine x={1} stroke={themeColors.yellow} strokeDasharray="3 3" />
              <Bar dataKey="profit_factor" radius={[0, 4, 4, 0]}>
                {pfData.map((entry, i) => (
                  <Cell key={i} fill={entry.profit_factor >= 1 ? themeColors.green : themeColors.red} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartContainer>

        {/* Correlation heatmap */}
        <ChartContainer title="Correlation Matrix" subtitle="Between symbols">
          {correlation && (correlation as Record<string, unknown>).symbols ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr>
                    <th className="p-2" />
                    {((correlation as Record<string, unknown>).symbols as string[]).map((s) => (
                      <th key={s} className="p-2 text-muted">{s}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {((correlation as Record<string, unknown>).symbols as string[]).map((s, i) => (
                    <tr key={s}>
                      <td className="p-2 text-muted">{s}</td>
                      {((correlation as Record<string, unknown>).matrix as number[][])[i].map((val, j) => {
                        const intensity = Math.abs(val);
                        const color = val > 0
                          ? themeRgba("--accent-rgb", intensity * 0.8)
                          : themeRgba("--red-rgb", intensity * 0.8);
                        return (
                          <td
                            key={j}
                            className="p-2 text-center"
                            style={{ backgroundColor: i === j ? "transparent" : color }}
                          >
                            {val.toFixed(2)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="py-8 text-center text-muted">No correlation data</p>
          )}
        </ChartContainer>
      </div>
    </div>
  );
}
