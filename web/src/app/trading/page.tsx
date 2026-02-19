"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  CandlestickData,
  HistogramData,
  IChartApi,
  ISeriesApi,
  Time,
} from "lightweight-charts";
import { CandlestickSeries, ColorType, createChart, HistogramSeries } from "lightweight-charts";
import { useCallback, useEffect, useRef, useState } from "react";
import ChartContainer from "@/components/shared/ChartContainer";
import DataTable from "@/components/shared/DataTable";
import { ChartSkeleton, TableSkeleton } from "@/components/shared/LoadingSkeleton";
import { useMarketPrices, useOHLC } from "@/hooks/useMarket";
import { useTrades } from "@/hooks/useTrades";
import { cancelOrder, getOrders, placeOrder } from "@/lib/api";
import { candleColors, darkChartOptions, themeColors } from "@/lib/chartTheme";
import { cn, formatCurrency, formatNumber } from "@/lib/formatters";
import { useNotificationStore } from "@/stores/notificationStore";
import { useUIStore } from "@/stores/uiStore";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const SYMBOLS = [
  "BTC/USD",
  "ETH/USD",
  "SOL/USD",
  "AAPL",
  "MSFT",
  "GOOGL",
  "AMZN",
  "TSLA",
  "NVDA",
  "META",
];

const TIMEFRAMES = [
  { label: "1m", value: "1m" },
  { label: "5m", value: "5m" },
  { label: "15m", value: "15m" },
  { label: "1h", value: "1h" },
  { label: "4h", value: "4h" },
  { label: "1D", value: "1d" },
] as const;

type OrderTab = "market" | "limit";
type OrderSide = "buy" | "sell";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function TradingPage() {
  const { selectedSymbol, setSelectedSymbol } = useUIStore();
  const [timeframe, setTimeframe] = useState("1h");

  return (
    <div className="flex gap-4 h-[calc(100vh-5rem)]">
      {/* Left Panel - 60% */}
      <div className="flex w-[60%] flex-col gap-4 min-w-0">
        <SymbolBar selectedSymbol={selectedSymbol} onSymbolChange={setSelectedSymbol} />
        <CandlestickChartPanel
          symbol={selectedSymbol}
          timeframe={timeframe}
          onTimeframeChange={setTimeframe}
        />
      </div>

      {/* Right Panel - 40% */}
      <div className="flex w-[40%] flex-col gap-4 min-w-0">
        <OrderForm symbol={selectedSymbol} />
        <ActiveOrders />
        <RecentFills symbol={selectedSymbol} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Symbol Bar
// ---------------------------------------------------------------------------
function SymbolBar({
  selectedSymbol,
  onSymbolChange,
}: {
  selectedSymbol: string;
  onSymbolChange: (s: string) => void;
}) {
  const { data: prices } = useMarketPrices();
  const currentPrice = prices?.[selectedSymbol];

  return (
    <div className="flex items-center gap-4 rounded-xl border border-border bg-card px-4 py-3">
      <select
        value={selectedSymbol}
        onChange={(e) => onSymbolChange(e.target.value)}
        className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm font-medium text-foreground outline-none focus:border-accent"
      >
        {SYMBOLS.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>

      {currentPrice && (
        <span className="text-lg font-semibold tabular-nums text-foreground">
          {formatCurrency(currentPrice)}
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Candlestick Chart Panel
// ---------------------------------------------------------------------------
function CandlestickChartPanel({
  symbol,
  timeframe,
  onTimeframeChange,
}: {
  symbol: string;
  timeframe: string;
  onTimeframeChange: (tf: string) => void;
}) {
  const { data: ohlcData, isLoading, isError, error } = useOHLC(symbol, timeframe);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const [chartReady, setChartReady] = useState(false);

  // Create chart once the container is mounted
  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      ...darkChartOptions,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: themeColors.muted,
      },
      width: container.clientWidth,
      height: container.clientHeight,
      handleScroll: true,
      handleScale: true,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      ...candleColors,
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: `${themeColors.accent}80`,
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;
    setChartReady(true);

    // Resize observer
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      setChartReady(false);
    };
  }, []);

  // Update data when ohlcData or chart readiness changes
  useEffect(() => {
    if (!chartReady || !ohlcData || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    const candles: CandlestickData<Time>[] = [];
    const volumes: HistogramData<Time>[] = [];

    for (const bar of ohlcData) {
      const time = (
        typeof bar.timestamp === "number"
          ? bar.timestamp
          : Math.floor(new Date(bar.timestamp as string).getTime() / 1000)
      ) as Time;

      const open = parseFloat(String(bar.open));
      const high = parseFloat(String(bar.high));
      const low = parseFloat(String(bar.low));
      const close = parseFloat(String(bar.close));
      const volume = parseFloat(String(bar.volume ?? 0));

      candles.push({ time, open, high, low, close });
      volumes.push({
        time,
        value: volume,
        color: close >= open ? `${themeColors.green}40` : `${themeColors.red}40`,
      });
    }

    candleSeriesRef.current.setData(candles);
    volumeSeriesRef.current.setData(volumes);

    if (candles.length > 0) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [ohlcData, chartReady]);

  const timeframeButtons = (
    <div className="flex gap-1">
      {TIMEFRAMES.map((tf) => (
        <button
          type="button"
          key={tf.value}
          onClick={() => onTimeframeChange(tf.value)}
          className={cn(
            "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
            timeframe === tf.value
              ? "bg-accent text-white"
              : "text-muted hover:bg-card-hover hover:text-foreground",
          )}
        >
          {tf.label}
        </button>
      ))}
    </div>
  );

  return (
    <ChartContainer
      title={symbol}
      subtitle="OHLCV Chart"
      actions={timeframeButtons}
      className="flex-1 flex flex-col min-h-0"
    >
      <div className="relative flex-1 min-h-0">
        {/* Chart div is always mounted so the ref is available */}
        <div ref={chartContainerRef} className="absolute inset-0" />

        {/* Overlay states */}
        {isLoading && (
          <div className="absolute inset-0 z-10">
            <ChartSkeleton height="h-full" />
          </div>
        )}
        {isError && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-card text-sm text-loss">
            Failed to load chart data: {(error as Error)?.message ?? "Unknown error"}
          </div>
        )}
        {!isLoading && !isError && (!ohlcData || ohlcData.length === 0) && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-card text-sm text-muted">
            No data available for {symbol} ({timeframe})
          </div>
        )}
      </div>
    </ChartContainer>
  );
}

// ---------------------------------------------------------------------------
// Order Form
// ---------------------------------------------------------------------------
function OrderForm({ symbol }: { symbol: string }) {
  const queryClient = useQueryClient();
  const addNotification = useNotificationStore((s) => s.add);

  const [tab, setTab] = useState<OrderTab>("market");
  const [side, setSide] = useState<OrderSide>("buy");
  const [quantity, setQuantity] = useState("");
  const [limitPrice, setLimitPrice] = useState("");

  const mutation = useMutation({
    mutationFn: placeOrder,
    onSuccess: () => {
      addNotification({
        type: "success",
        title: "Order placed",
        message: `${side.toUpperCase()} ${quantity} ${symbol} at ${tab === "limit" ? `limit $${limitPrice}` : "market"}`,
      });
      setQuantity("");
      setLimitPrice("");
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["trades"] });
    },
    onError: (err: Error) => {
      addNotification({
        type: "error",
        title: "Order failed",
        message: err.message,
      });
    },
  });

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const qty = parseFloat(quantity);
      if (Number.isNaN(qty) || qty <= 0) {
        addNotification({ type: "error", title: "Invalid quantity" });
        return;
      }
      if (tab === "limit") {
        const lp = parseFloat(limitPrice);
        if (Number.isNaN(lp) || lp <= 0) {
          addNotification({ type: "error", title: "Invalid limit price" });
          return;
        }
      }

      mutation.mutate({
        symbol,
        side,
        order_type: tab,
        quantity: parseFloat(quantity),
        ...(tab === "limit" ? { limit_price: parseFloat(limitPrice) } : {}),
      });
    },
    [symbol, side, tab, quantity, limitPrice, mutation, addNotification],
  );

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h3 className="mb-3 text-sm font-medium text-foreground">Place Order</h3>

      {/* Market / Limit tabs */}
      <div className="mb-3 flex rounded-lg border border-border overflow-hidden">
        {(["market", "limit"] as const).map((t) => (
          <button
            type="button"
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "flex-1 py-1.5 text-xs font-medium uppercase tracking-wider transition-colors",
              tab === t ? "bg-accent text-white" : "bg-background text-muted hover:text-foreground",
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Buy / Sell toggle */}
      <div className="mb-4 flex gap-2">
        <button
          type="button"
          onClick={() => setSide("buy")}
          className={cn(
            "flex-1 rounded-lg py-2 text-sm font-semibold transition-colors",
            side === "buy"
              ? "bg-profit text-white"
              : "border border-border bg-background text-muted hover:text-foreground",
          )}
        >
          BUY
        </button>
        <button
          type="button"
          onClick={() => setSide("sell")}
          className={cn(
            "flex-1 rounded-lg py-2 text-sm font-semibold transition-colors",
            side === "sell"
              ? "bg-loss text-white"
              : "border border-border bg-background text-muted hover:text-foreground",
          )}
        >
          SELL
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Quantity */}
        <div>
          <label htmlFor="order-quantity" className="mb-1 block text-xs text-muted">
            Quantity
          </label>
          <input
            id="order-quantity"
            type="number"
            min="0"
            step="any"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="0.00"
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted/50 focus:border-accent tabular-nums"
          />
        </div>

        {/* Limit price (conditional) */}
        {tab === "limit" && (
          <div>
            <label htmlFor="order-limit-price" className="mb-1 block text-xs text-muted">
              Limit Price
            </label>
            <input
              id="order-limit-price"
              type="number"
              min="0"
              step="any"
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
              placeholder="0.00"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted/50 focus:border-accent tabular-nums"
            />
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={mutation.isPending}
          className={cn(
            "w-full rounded-lg py-2.5 text-sm font-semibold text-white transition-colors disabled:opacity-50",
            side === "buy" ? "bg-profit hover:bg-profit/90" : "bg-loss hover:bg-loss/90",
          )}
        >
          {mutation.isPending ? "Placing..." : `${side === "buy" ? "Buy" : "Sell"} ${symbol}`}
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Active Orders
// ---------------------------------------------------------------------------
function ActiveOrders() {
  const queryClient = useQueryClient();
  const addNotification = useNotificationStore((s) => s.add);

  const {
    data: orders,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["orders"],
    queryFn: getOrders,
    refetchInterval: 5000,
  });

  const cancelMutation = useMutation({
    mutationFn: cancelOrder,
    onSuccess: () => {
      addNotification({ type: "success", title: "Order cancelled" });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
    onError: (err: Error) => {
      addNotification({ type: "error", title: "Cancel failed", message: err.message });
    },
  });

  const activeOrders = (orders ?? []).filter(
    (o) => o.status === "open" || o.status === "pending" || o.status === "new",
  );

  const columns = [
    {
      key: "symbol",
      header: "Symbol",
      render: (row: Record<string, unknown>) => (
        <span className="font-medium text-foreground">{String(row.symbol)}</span>
      ),
    },
    {
      key: "side",
      header: "Side",
      render: (row: Record<string, unknown>) => (
        <span
          className={cn(
            "text-xs font-semibold uppercase",
            String(row.side) === "buy" ? "text-profit" : "text-loss",
          )}
        >
          {String(row.side)}
        </span>
      ),
    },
    {
      key: "order_type",
      header: "Type",
      render: (row: Record<string, unknown>) => (
        <span className="text-xs uppercase text-muted">{String(row.order_type)}</span>
      ),
    },
    {
      key: "quantity",
      header: "Qty",
      render: (row: Record<string, unknown>) => (
        <span className="tabular-nums">{formatNumber(String(row.quantity))}</span>
      ),
    },
    {
      key: "limit_price",
      header: "Price",
      render: (row: Record<string, unknown>) =>
        row.limit_price ? (
          <span className="tabular-nums">{formatCurrency(String(row.limit_price))}</span>
        ) : (
          <span className="text-muted">MKT</span>
        ),
    },
    {
      key: "actions",
      header: "",
      render: (row: Record<string, unknown>) => (
        <button
          type="button"
          onClick={() => cancelMutation.mutate(String(row.id))}
          disabled={cancelMutation.isPending}
          className="rounded px-2 py-0.5 text-xs font-medium text-loss hover:bg-loss/10 transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
      ),
      className: "text-right",
    },
  ];

  return (
    <div className="rounded-xl border border-border bg-card p-4 flex-1 min-h-0 overflow-auto">
      <h3 className="mb-3 text-sm font-medium text-foreground">Active Orders</h3>
      {isLoading ? (
        <TableSkeleton rows={3} />
      ) : isError ? (
        <p className="py-4 text-center text-sm text-loss">Failed to load orders</p>
      ) : (
        <DataTable
          columns={columns}
          data={activeOrders}
          emptyMessage="No active orders"
          maxRows={10}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Recent Fills
// ---------------------------------------------------------------------------
function RecentFills({ symbol }: { symbol: string }) {
  const { data: trades, isLoading, isError } = useTrades({ symbol, limit: 20 });

  const columns = [
    {
      key: "side",
      header: "Side",
      render: (row: Record<string, unknown>) => (
        <span
          className={cn(
            "text-xs font-semibold uppercase",
            String(row.side) === "buy" ? "text-profit" : "text-loss",
          )}
        >
          {String(row.side)}
        </span>
      ),
    },
    {
      key: "quantity",
      header: "Qty",
      render: (row: Record<string, unknown>) => (
        <span className="tabular-nums">{formatNumber(String(row.quantity))}</span>
      ),
    },
    {
      key: "price",
      header: "Price",
      render: (row: Record<string, unknown>) => (
        <span className="tabular-nums">{formatCurrency(String(row.price))}</span>
      ),
    },
    {
      key: "strategy",
      header: "Strategy",
      render: (row: Record<string, unknown>) => (
        <span className="text-xs text-muted">{String(row.strategy ?? "-")}</span>
      ),
    },
    {
      key: "timestamp",
      header: "Time",
      render: (row: Record<string, unknown>) => {
        const ts = String(row.timestamp ?? "");
        if (!ts) return <span className="text-muted">-</span>;
        const d = new Date(ts);
        return (
          <span className="text-xs tabular-nums text-muted">
            {d.toLocaleTimeString("en-US", {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </span>
        );
      },
    },
  ];

  return (
    <div className="rounded-xl border border-border bg-card p-4 flex-1 min-h-0 overflow-auto">
      <h3 className="mb-3 text-sm font-medium text-foreground">
        Recent Fills
        <span className="ml-2 text-xs font-normal text-muted">{symbol}</span>
      </h3>
      {isLoading ? (
        <TableSkeleton rows={4} />
      ) : isError ? (
        <p className="py-4 text-center text-sm text-loss">Failed to load trades</p>
      ) : (
        <DataTable
          columns={columns}
          data={(trades as Record<string, unknown>[]) ?? []}
          emptyMessage={`No fills for ${symbol}`}
          maxRows={20}
        />
      )}
    </div>
  );
}
