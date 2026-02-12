"use client";

import Link from "next/link";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { DollarSign, TrendingUp, Briefcase, Banknote } from "lucide-react";

import { usePortfolio, usePositions, usePnL, useEquityCurve } from "@/hooks/usePortfolio";
import { useSignals } from "@/hooks/useTrades";
import { useDrawdownStatus } from "@/hooks/useRisk";
import { useSparklines } from "@/hooks/useMarket";

import StatCard from "@/components/shared/StatCard";
import ChartContainer from "@/components/shared/ChartContainer";
import DataTable from "@/components/shared/DataTable";
import { StatCardSkeleton, ChartSkeleton, TableSkeleton } from "@/components/shared/LoadingSkeleton";
import { formatCurrency, formatPnL, formatPercent, formatTimeAgo, cn } from "@/lib/formatters";
import { rechartsColors } from "@/lib/chartTheme";

import type { Position, Signal, DrawdownStatus, EquityPoint, SparklineData } from "@/types";

// ---------------------------------------------------------------------------
// Stat Cards Section
// ---------------------------------------------------------------------------

function StatCards() {
  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio();
  const { data: pnl, isLoading: pnlLoading } = usePnL("1d");

  if (portfolioLoading || pnlLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <StatCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  const totalValue = portfolio?.total_value ?? 0;
  const cash = portfolio?.cash ?? 0;
  const positionCount = (portfolio?.positions as unknown[] | undefined)?.length ?? 0;

  const dailyPnl = pnl?.total_pnl ?? 0;
  const dailyPnlNum = typeof dailyPnl === "string" ? parseFloat(dailyPnl) : (dailyPnl as number);
  const dailyTrend: "up" | "down" | "neutral" =
    dailyPnlNum > 0 ? "up" : dailyPnlNum < 0 ? "down" : "neutral";

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        title="Total Value"
        value={formatCurrency(totalValue as string | number)}
        icon={DollarSign}
        trend="neutral"
      />
      <StatCard
        title="Daily P&L"
        value={formatPnL(dailyPnl as string | number)}
        subtitle="Today"
        icon={TrendingUp}
        trend={dailyTrend}
      />
      <StatCard
        title="Open Positions"
        value={String(positionCount)}
        icon={Briefcase}
        trend="neutral"
      />
      <StatCard
        title="Cash"
        value={formatCurrency(cash as string | number)}
        icon={Banknote}
        trend="neutral"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mini Equity Curve
// ---------------------------------------------------------------------------

function EquityCurveChart() {
  const { data, isLoading, error } = useEquityCurve("1M");

  if (isLoading) {
    return (
      <ChartContainer title="Equity Curve" subtitle="30-day performance">
        <ChartSkeleton height="h-56" />
      </ChartContainer>
    );
  }

  const points: EquityPoint[] = data?.points ?? [];

  if (error || points.length === 0) {
    return (
      <ChartContainer title="Equity Curve" subtitle="30-day performance">
        <div className="flex h-56 items-center justify-center text-sm text-muted">
          {error ? "Failed to load equity curve" : "No equity data available"}
        </div>
      </ChartContainer>
    );
  }

  const formatted = points.map((p) => ({
    date: new Date(p.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    value: p.value,
  }));

  return (
    <ChartContainer title="Equity Curve" subtitle="30-day performance">
      <ResponsiveContainer width="100%" height={224}>
        <AreaChart data={formatted} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={rechartsColors.green} stopOpacity={0.3} />
              <stop offset="100%" stopColor={rechartsColors.green} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={rechartsColors.grid} vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: rechartsColors.text }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: rechartsColors.text }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => formatCurrency(v, 0)}
            width={72}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: rechartsColors.background,
              border: `1px solid ${rechartsColors.grid}`,
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: rechartsColors.text }}
            formatter={(value) => [formatCurrency(Number(value ?? 0)), "Value"]}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={rechartsColors.green}
            strokeWidth={2}
            fill="url(#equityGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartContainer>
  );
}

// ---------------------------------------------------------------------------
// Active Positions Table
// ---------------------------------------------------------------------------

function ActivePositions() {
  const { data, isLoading, error } = usePositions();

  if (isLoading) {
    return (
      <ChartContainer title="Active Positions" subtitle="Top 8 holdings">
        <TableSkeleton rows={5} />
      </ChartContainer>
    );
  }

  if (error) {
    return (
      <ChartContainer title="Active Positions" subtitle="Top 8 holdings">
        <p className="py-8 text-center text-sm text-muted">Failed to load positions</p>
      </ChartContainer>
    );
  }

  const positions = (data ?? []) as unknown as Position[];

  const columns = [
    { key: "symbol", header: "Symbol", render: (row: Position) => (
      <span className="font-medium text-foreground">{row.symbol}</span>
    )},
    { key: "quantity", header: "Qty", render: (row: Position) => (
      <span className="font-mono text-sm">{row.quantity}</span>
    )},
    { key: "current_price", header: "Price", render: (row: Position) => (
      <span className="font-mono text-sm">{formatCurrency(row.current_price)}</span>
    )},
    { key: "unrealized_pnl", header: "P&L", render: (row: Position) => {
      const pnl = parseFloat(row.unrealized_pnl);
      return (
        <span className={cn("font-mono text-sm", pnl >= 0 ? "text-profit" : "text-loss")}>
          {formatPnL(row.unrealized_pnl)}
        </span>
      );
    }},
  ];

  return (
    <ChartContainer
      title="Active Positions"
      subtitle="Top 8 holdings"
      actions={
        <Link href="/portfolio" className="text-xs text-accent hover:underline">
          View all
        </Link>
      }
    >
      <DataTable
        columns={columns}
        data={positions}
        maxRows={8}
        emptyMessage="No open positions"
      />
    </ChartContainer>
  );
}

// ---------------------------------------------------------------------------
// Recent Signals Feed
// ---------------------------------------------------------------------------

const directionBadge: Record<string, { label: string; className: string }> = {
  buy:  { label: "BUY",  className: "bg-profit/15 text-profit" },
  sell: { label: "SELL", className: "bg-loss/15 text-loss" },
  hold: { label: "HOLD", className: "bg-muted/15 text-muted" },
};

function RecentSignals() {
  const { data, isLoading, error } = useSignals({ limit: 10 });

  if (isLoading) {
    return (
      <ChartContainer title="Recent Signals" subtitle="Last 10 signals">
        <TableSkeleton rows={5} />
      </ChartContainer>
    );
  }

  if (error) {
    return (
      <ChartContainer title="Recent Signals" subtitle="Last 10 signals">
        <p className="py-8 text-center text-sm text-muted">Failed to load signals</p>
      </ChartContainer>
    );
  }

  const signals = (data ?? []) as unknown as Signal[];

  return (
    <ChartContainer title="Recent Signals" subtitle="Last 10 signals">
      {signals.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted">No recent signals</p>
      ) : (
        <div className="space-y-2">
          {signals.slice(0, 10).map((sig) => {
            const badge = directionBadge[sig.direction] ?? directionBadge.hold;
            return (
              <div
                key={sig.id}
                className="flex items-center gap-3 rounded-lg border border-border/50 px-3 py-2"
              >
                <span
                  className={cn(
                    "inline-flex w-12 items-center justify-center rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase",
                    badge.className,
                  )}
                >
                  {badge.label}
                </span>
                <span className="w-16 font-medium text-foreground text-sm">{sig.symbol}</span>
                <span className="text-xs text-muted">{sig.strategy}</span>
                <div className="ml-auto flex items-center gap-3">
                  {/* Confidence bar */}
                  <div className="flex items-center gap-1.5">
                    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-border">
                      <div
                        className={cn(
                          "h-full rounded-full",
                          sig.confidence >= 0.7
                            ? "bg-profit"
                            : sig.confidence >= 0.4
                              ? "bg-warning"
                              : "bg-loss",
                        )}
                        style={{ width: `${Math.round(sig.confidence * 100)}%` }}
                      />
                    </div>
                    <span className="w-9 text-right font-mono text-[10px] text-muted">
                      {Math.round(sig.confidence * 100)}%
                    </span>
                  </div>
                  <span className="w-14 text-right text-[10px] text-muted">
                    {formatTimeAgo(sig.timestamp)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </ChartContainer>
  );
}

// ---------------------------------------------------------------------------
// Risk Status
// ---------------------------------------------------------------------------

function RiskProgressBar({
  label,
  current,
  limit,
  unit = "%",
}: {
  label: string;
  current: number;
  limit: number;
  unit?: string;
}) {
  const pct = limit > 0 ? Math.min((current / limit) * 100, 100) : 0;
  const color =
    pct >= 80 ? "bg-loss" : pct >= 50 ? "bg-warning" : "bg-profit";

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="font-mono text-foreground">
          {unit === "%" ? `${current.toFixed(1)}%` : current} / {unit === "%" ? `${limit.toFixed(1)}%` : limit}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-border">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function RiskStatus() {
  const { data, isLoading, error } = useDrawdownStatus();

  if (isLoading) {
    return (
      <ChartContainer title="Risk Status">
        <ChartSkeleton height="h-32" />
      </ChartContainer>
    );
  }

  if (error) {
    return (
      <ChartContainer title="Risk Status">
        <p className="py-8 text-center text-sm text-muted">Failed to load risk data</p>
      </ChartContainer>
    );
  }

  const dd = data as unknown as DrawdownStatus | undefined;

  if (!dd) {
    return (
      <ChartContainer title="Risk Status">
        <p className="py-8 text-center text-sm text-muted">No risk data available</p>
      </ChartContainer>
    );
  }

  return (
    <ChartContainer title="Risk Status" subtitle="Drawdown & exposure limits">
      <div className="space-y-4">
        <RiskProgressBar
          label="Daily Drawdown"
          current={dd.daily_pct}
          limit={dd.daily_limit}
        />
        <RiskProgressBar
          label="Weekly Drawdown"
          current={dd.weekly_pct}
          limit={dd.weekly_limit}
        />
        <RiskProgressBar
          label="Position Count"
          current={dd.positions_used}
          limit={dd.positions_limit}
          unit=""
        />
      </div>
    </ChartContainer>
  );
}

// ---------------------------------------------------------------------------
// Market Overview with Sparklines
// ---------------------------------------------------------------------------

function MiniSparkline({ prices, positive }: { prices: number[]; positive: boolean }) {
  if (!prices || prices.length < 2) return null;
  const data = prices.map((p, i) => ({ i, v: p }));
  const color = positive ? rechartsColors.green : rechartsColors.red;
  return (
    <ResponsiveContainer width={80} height={28}>
      <LineChart data={data} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
        <Line
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function MarketOverview() {
  const { data, isLoading, error } = useSparklines();

  if (isLoading) {
    return (
      <ChartContainer title="Market Overview" subtitle="Watchlist">
        <TableSkeleton rows={5} />
      </ChartContainer>
    );
  }

  if (error) {
    return (
      <ChartContainer title="Market Overview" subtitle="Watchlist">
        <p className="py-8 text-center text-sm text-muted">Failed to load market data</p>
      </ChartContainer>
    );
  }

  const sparklines = data as unknown as Record<string, SparklineData> | undefined;
  const symbols = sparklines ? Object.keys(sparklines) : [];

  if (symbols.length === 0) {
    return (
      <ChartContainer title="Market Overview" subtitle="Watchlist">
        <p className="py-8 text-center text-sm text-muted">No watchlist data</p>
      </ChartContainer>
    );
  }

  return (
    <ChartContainer title="Market Overview" subtitle="Watchlist">
      <div className="space-y-1">
        {symbols.map((symbol) => {
          const item = sparklines![symbol];
          const positive = item.change_pct >= 0;
          return (
            <div
              key={symbol}
              className="flex items-center gap-3 rounded-lg px-3 py-1.5 hover:bg-card-hover/50"
            >
              <span className="w-16 text-sm font-medium text-foreground">{symbol}</span>
              <MiniSparkline prices={item.prices} positive={positive} />
              <span className="ml-auto font-mono text-sm text-foreground">
                {formatCurrency(item.current)}
              </span>
              <span
                className={cn(
                  "w-16 text-right font-mono text-xs",
                  positive ? "text-profit" : "text-loss",
                )}
              >
                {formatPercent(item.change_pct)}
              </span>
            </div>
          );
        })}
      </div>
    </ChartContainer>
  );
}

// ---------------------------------------------------------------------------
// Dashboard Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <StatCards />

      {/* Equity Curve */}
      <EquityCurveChart />

      {/* Two-column: Positions + Signals */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ActivePositions />
        <RecentSignals />
      </div>

      {/* Two-column: Risk Status + Market Overview */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <RiskStatus />
        <MarketOverview />
      </div>
    </div>
  );
}
