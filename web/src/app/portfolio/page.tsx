"use client";

import { useState, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  Target,
  BarChart3,
} from "lucide-react";
import { useEquityCurve, useAllocation, usePnL, usePositions } from "@/hooks/usePortfolio";
import { getTrades } from "@/lib/api";
import StatCard from "@/components/shared/StatCard";
import ChartContainer from "@/components/shared/ChartContainer";
import DataTable from "@/components/shared/DataTable";
import {
  StatCardSkeleton,
  ChartSkeleton,
  TableSkeleton,
} from "@/components/shared/LoadingSkeleton";
import {
  formatCurrency,
  formatPnL,
  formatPercent,
  formatTimestamp,
  cn,
} from "@/lib/formatters";
import { themeColors, seriesColors } from "@/lib/chartTheme";
import type { Position, Trade, PnLSummary } from "@/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EQUITY_RANGES = ["1D", "1W", "1M", "3M", "1Y", "ALL"] as const;
type EquityRange = (typeof EQUITY_RANGES)[number];

const PIE_COLORS = seriesColors;

const TRADES_PER_PAGE = 20;

// ---------------------------------------------------------------------------
// Equity Curve tooltip
// ---------------------------------------------------------------------------

interface EquityTooltipPayload {
  value: number;
  payload: { timestamp: string; value: number };
}

function EquityTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: EquityTooltipPayload[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0];
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-lg">
      <p className="text-xs text-muted">
        {new Date(point.payload.timestamp).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        })}
      </p>
      <p className="text-sm font-semibold text-foreground">
        {formatCurrency(point.value)}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom pie legend
// ---------------------------------------------------------------------------

interface LegendEntry {
  value: string;
  color?: string;
}

function PieLegend({ payload }: { payload?: LegendEntry[] }) {
  if (!payload) return null;
  return (
    <div className="mt-3 flex flex-wrap justify-center gap-x-4 gap-y-1">
      {payload.map((entry) => (
        <div key={entry.value} className="flex items-center gap-1.5 text-xs text-muted">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          {entry.value}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function PortfolioPage() {
  // -- Equity curve ----------------------------------------------------------
  const [equityRange, setEquityRange] = useState<EquityRange>("1M");
  const {
    data: equityData,
    isLoading: equityLoading,
    error: equityError,
  } = useEquityCurve(equityRange);

  const equityPoints = useMemo(
    () =>
      equityData?.points?.map((p: { timestamp: string; value: number }) => ({
        timestamp: p.timestamp,
        value: p.value,
      })) ?? [],
    [equityData],
  );

  // -- Allocation ------------------------------------------------------------
  const [allocationView, setAllocationView] = useState<"type" | "sector">("type");
  const {
    data: allocationData,
    isLoading: allocationLoading,
    error: allocationError,
  } = useAllocation();

  const { allocationSlices, cashPct } = useMemo(() => {
    if (!allocationData) return { allocationSlices: [], cashPct: 0 };

    const raw = allocationData as Record<string, unknown>;
    const byType = (raw.by_type ?? raw.byType ?? {}) as Record<string, number>;
    const bySector = (raw.by_sector ?? raw.bySector ?? {}) as Record<string, number>;
    const cash = ((raw.cash_pct ?? raw.cashPct ?? 0) as number);

    const source = allocationView === "type" ? byType : bySector;
    const slices = Object.entries(source).map(([name, value]) => ({ name, value }));
    return { allocationSlices: slices, cashPct: cash };
  }, [allocationData, allocationView]);

  // -- P&L -------------------------------------------------------------------
  const { data: pnlRaw, isLoading: pnlLoading, error: pnlError } = usePnL();
  const pnl = pnlRaw as PnLSummary | undefined;

  // -- Positions --------------------------------------------------------------
  const {
    data: positionsRaw,
    isLoading: positionsLoading,
    error: positionsError,
  } = usePositions();
  const positions = (positionsRaw ?? []) as unknown as Position[];

  const [posSortKey, setPosSortKey] = useState<keyof Position>("symbol");
  const [posSortDir, setPosSortDir] = useState<"asc" | "desc">("asc");

  const sortedPositions = useMemo(() => {
    const sorted = [...positions].sort((a, b) => {
      const aVal = a[posSortKey] ?? "";
      const bVal = b[posSortKey] ?? "";
      const aNum = parseFloat(String(aVal));
      const bNum = parseFloat(String(bVal));

      if (!isNaN(aNum) && !isNaN(bNum)) {
        return posSortDir === "asc" ? aNum - bNum : bNum - aNum;
      }
      const cmp = String(aVal).localeCompare(String(bVal));
      return posSortDir === "asc" ? cmp : -cmp;
    });
    return sorted;
  }, [positions, posSortKey, posSortDir]);

  const handleSort = useCallback(
    (key: keyof Position) => {
      if (posSortKey === key) {
        setPosSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setPosSortKey(key);
        setPosSortDir("asc");
      }
    },
    [posSortKey],
  );

  const sortIndicator = useCallback(
    (key: keyof Position) => {
      if (posSortKey !== key) return "";
      return posSortDir === "asc" ? " \u25B2" : " \u25BC";
    },
    [posSortKey, posSortDir],
  );

  // -- Trades (paginated) ----------------------------------------------------
  const [tradesPage, setTradesPage] = useState(0);
  const offset = tradesPage * TRADES_PER_PAGE;

  const {
    data: tradesRaw,
    isLoading: tradesLoading,
    error: tradesError,
  } = useQuery({
    queryKey: ["trades", { limit: TRADES_PER_PAGE, offset }],
    queryFn: () => getTrades({ limit: TRADES_PER_PAGE, offset }),
    refetchInterval: 15000,
  });
  const trades = (tradesRaw ?? []) as unknown as Trade[];

  // -- Column definitions for positions table --------------------------------
  const positionColumns = useMemo(
    () => [
      {
        key: "symbol" as const,
        header: `Symbol${sortIndicator("symbol")}`,
        render: (row: Position) => (
          <span className="font-medium text-foreground">{row.symbol}</span>
        ),
      },
      {
        key: "quantity" as const,
        header: `Quantity${sortIndicator("quantity")}`,
        render: (row: Position) => parseFloat(row.quantity).toLocaleString(),
      },
      {
        key: "avg_entry_price" as const,
        header: `Avg Entry${sortIndicator("avg_entry_price")}`,
        render: (row: Position) => formatCurrency(row.avg_entry_price),
      },
      {
        key: "current_price" as const,
        header: `Current Price${sortIndicator("current_price")}`,
        render: (row: Position) => formatCurrency(row.current_price),
      },
      {
        key: "market_value" as const,
        header: `Market Value${sortIndicator("market_value")}`,
        render: (row: Position) => formatCurrency(row.market_value),
      },
      {
        key: "unrealized_pnl" as const,
        header: `Unrealized P&L${sortIndicator("unrealized_pnl")}`,
        render: (row: Position) => {
          const val = parseFloat(row.unrealized_pnl);
          return (
            <span className={cn(val >= 0 ? "text-profit" : "text-loss")}>
              {formatPnL(row.unrealized_pnl)}
            </span>
          );
        },
      },
      {
        key: "asset_type" as const,
        header: `Asset Type${sortIndicator("asset_type")}`,
        render: (row: Position) => (
          <span className="rounded bg-border/40 px-2 py-0.5 text-xs capitalize text-muted">
            {row.asset_type}
          </span>
        ),
      },
    ],
    [sortIndicator],
  );

  // -- Column definitions for trades table -----------------------------------
  const tradeColumns = useMemo(
    () => [
      {
        key: "timestamp" as const,
        header: "Time",
        render: (row: Trade) => (
          <span className="text-muted">{formatTimestamp(row.timestamp)}</span>
        ),
      },
      {
        key: "symbol" as const,
        header: "Symbol",
        render: (row: Trade) => (
          <span className="font-medium text-foreground">{row.symbol}</span>
        ),
      },
      {
        key: "side" as const,
        header: "Side",
        render: (row: Trade) => (
          <span
            className={cn(
              "inline-block rounded px-2 py-0.5 text-xs font-medium uppercase",
              row.side === "buy"
                ? "bg-profit/15 text-profit"
                : "bg-loss/15 text-loss",
            )}
          >
            {row.side}
          </span>
        ),
      },
      {
        key: "quantity" as const,
        header: "Quantity",
        render: (row: Trade) => parseFloat(row.quantity).toLocaleString(),
      },
      {
        key: "price" as const,
        header: "Price",
        render: (row: Trade) => formatCurrency(row.price),
      },
      {
        key: "strategy" as const,
        header: "Strategy",
        render: (row: Trade) => (
          <span className="text-muted">{row.strategy}</span>
        ),
      },
    ],
    [],
  );

  // -- Helpers ---------------------------------------------------------------
  const realizedVal = pnl ? parseFloat(pnl.realized_pnl) : 0;
  const unrealizedVal = pnl ? parseFloat(pnl.unrealized_pnl) : 0;

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Portfolio
        </h1>
        <p className="mt-1 text-sm text-muted">
          Equity, allocation, positions, and trade history
        </p>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* P&L stat cards                                                      */}
      {/* ------------------------------------------------------------------ */}
      <section>
        {pnlLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <StatCardSkeleton key={i} />
            ))}
          </div>
        ) : pnlError ? (
          <ErrorBanner message="Failed to load P&L data" />
        ) : pnl ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Realized P&L"
              value={formatPnL(pnl.realized_pnl)}
              icon={realizedVal >= 0 ? TrendingUp : TrendingDown}
              trend={realizedVal >= 0 ? "up" : "down"}
            />
            <StatCard
              title="Unrealized P&L"
              value={formatPnL(pnl.unrealized_pnl)}
              icon={unrealizedVal >= 0 ? TrendingUp : TrendingDown}
              trend={unrealizedVal >= 0 ? "up" : "down"}
            />
            <StatCard
              title="Win Rate"
              value={formatPercent(pnl.win_rate)}
              subtitle={`${pnl.winning_trades} / ${pnl.total_trades} winning`}
              icon={Target}
              trend={pnl.win_rate >= 50 ? "up" : pnl.win_rate > 0 ? "down" : "neutral"}
            />
            <StatCard
              title="Total Trades"
              value={String(pnl.total_trades)}
              icon={BarChart3}
            />
          </div>
        ) : (
          <EmptyBanner message="No P&L data available" />
        )}
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Charts row: Equity Curve + Allocation Pie                           */}
      {/* ------------------------------------------------------------------ */}
      <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Equity curve (takes 2/3 width on xl) */}
        <div className="xl:col-span-2">
          <ChartContainer
            title="Equity Curve"
            subtitle="Portfolio value over time"
            actions={
              <div className="flex rounded-lg border border-border">
                {EQUITY_RANGES.map((range) => (
                  <button
                    key={range}
                    onClick={() => setEquityRange(range)}
                    className={cn(
                      "px-2.5 py-1 text-xs font-medium transition-colors",
                      equityRange === range
                        ? "bg-accent text-white"
                        : "text-muted hover:text-foreground",
                      range === EQUITY_RANGES[0] && "rounded-l-lg",
                      range === EQUITY_RANGES[EQUITY_RANGES.length - 1] && "rounded-r-lg",
                    )}
                  >
                    {range}
                  </button>
                ))}
              </div>
            }
          >
            {equityLoading ? (
              <ChartSkeleton height="h-72" />
            ) : equityError ? (
              <ErrorBanner message="Failed to load equity curve" />
            ) : equityPoints.length === 0 ? (
              <EmptyBanner message="No equity data for this range" />
            ) : (
              <ResponsiveContainer width="100%" height={288}>
                <AreaChart data={equityPoints} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={themeColors.green} stopOpacity={0.3} />
                      <stop offset="100%" stopColor={themeColors.green} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="timestamp"
                    tickFormatter={(ts: string) =>
                      new Date(ts).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                      })
                    }
                    tick={{ fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    minTickGap={40}
                  />
                  <YAxis
                    tickFormatter={(v: number) => formatCurrency(v, 0)}
                    tick={{ fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={72}
                  />
                  <Tooltip content={<EquityTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={themeColors.green}
                    strokeWidth={2}
                    fill="url(#equityGrad)"
                    dot={false}
                    activeDot={{ r: 4, fill: themeColors.green, strokeWidth: 0 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </ChartContainer>
        </div>

        {/* Asset allocation pie (1/3 width on xl) */}
        <div>
          <ChartContainer
            title="Asset Allocation"
            actions={
              <div className="flex rounded-lg border border-border">
                <button
                  onClick={() => setAllocationView("type")}
                  className={cn(
                    "rounded-l-lg px-2.5 py-1 text-xs font-medium transition-colors",
                    allocationView === "type"
                      ? "bg-accent text-white"
                      : "text-muted hover:text-foreground",
                  )}
                >
                  By Type
                </button>
                <button
                  onClick={() => setAllocationView("sector")}
                  className={cn(
                    "rounded-r-lg px-2.5 py-1 text-xs font-medium transition-colors",
                    allocationView === "sector"
                      ? "bg-accent text-white"
                      : "text-muted hover:text-foreground",
                  )}
                >
                  By Sector
                </button>
              </div>
            }
          >
            {allocationLoading ? (
              <ChartSkeleton height="h-72" />
            ) : allocationError ? (
              <ErrorBanner message="Failed to load allocation data" />
            ) : allocationSlices.length === 0 ? (
              <EmptyBanner message="No allocation data" />
            ) : (
              <ResponsiveContainer width="100%" height={288}>
                <PieChart>
                  <Pie
                    data={allocationSlices}
                    cx="50%"
                    cy="45%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                    dataKey="value"
                    nameKey="name"
                    stroke="none"
                  >
                    {allocationSlices.map((_, idx) => (
                      <Cell
                        key={idx}
                        fill={PIE_COLORS[idx % PIE_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Legend content={<PieLegend />} />
                  {/* Center label rendered as custom SVG text */}
                  <text
                    x="50%"
                    y="45%"
                    textAnchor="middle"
                    dominantBaseline="central"
                    className="fill-foreground text-sm font-semibold"
                  >
                    {`Cash: ${cashPct.toFixed(1)}%`}
                  </text>
                </PieChart>
              </ResponsiveContainer>
            )}
          </ChartContainer>
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Positions table                                                     */}
      {/* ------------------------------------------------------------------ */}
      <section>
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-4 text-sm font-medium text-foreground">
            Open Positions
          </h3>
          {positionsLoading ? (
            <TableSkeleton rows={6} />
          ) : positionsError ? (
            <ErrorBanner message="Failed to load positions" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    {positionColumns.map((col) => (
                      <th
                        key={col.key}
                        className="cursor-pointer select-none px-3 py-2 text-left text-xs font-medium text-muted hover:text-foreground"
                        onClick={() => handleSort(col.key as keyof Position)}
                      >
                        {col.header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedPositions.length === 0 ? (
                    <tr>
                      <td
                        colSpan={positionColumns.length}
                        className="px-3 py-8 text-center text-muted"
                      >
                        No open positions
                      </td>
                    </tr>
                  ) : (
                    sortedPositions.map((pos, i) => (
                      <tr
                        key={`${pos.symbol}-${i}`}
                        className="border-b border-border/50 hover:bg-card-hover/50"
                      >
                        {positionColumns.map((col) => (
                          <td key={col.key} className="px-3 py-2">
                            {col.render(pos)}
                          </td>
                        ))}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Trade history table (paginated)                                     */}
      {/* ------------------------------------------------------------------ */}
      <section>
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-medium text-foreground">
              Trade History
            </h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setTradesPage((p) => Math.max(0, p - 1))}
                disabled={tradesPage === 0}
                className={cn(
                  "rounded-lg border border-border px-3 py-1 text-xs font-medium transition-colors",
                  tradesPage === 0
                    ? "cursor-not-allowed text-muted opacity-50"
                    : "text-foreground hover:bg-card-hover",
                )}
              >
                Prev
              </button>
              <span className="text-xs text-muted">
                Page {tradesPage + 1}
              </span>
              <button
                onClick={() => setTradesPage((p) => p + 1)}
                disabled={trades.length < TRADES_PER_PAGE}
                className={cn(
                  "rounded-lg border border-border px-3 py-1 text-xs font-medium transition-colors",
                  trades.length < TRADES_PER_PAGE
                    ? "cursor-not-allowed text-muted opacity-50"
                    : "text-foreground hover:bg-card-hover",
                )}
              >
                Next
              </button>
            </div>
          </div>

          {tradesLoading ? (
            <TableSkeleton rows={10} />
          ) : tradesError ? (
            <ErrorBanner message="Failed to load trade history" />
          ) : (
            <DataTable
              columns={tradeColumns}
              data={trades}
              emptyMessage="No trades recorded yet"
            />
          )}
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Utility components
// ---------------------------------------------------------------------------

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center rounded-lg border border-loss/20 bg-loss/5 px-4 py-8">
      <p className="text-sm text-loss">{message}</p>
    </div>
  );
}

function EmptyBanner({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center rounded-lg border border-border bg-card px-4 py-8">
      <p className="text-sm text-muted">{message}</p>
    </div>
  );
}
