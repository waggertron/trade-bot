import { type DeepPartial, type ChartOptions, ColorType } from "lightweight-charts";

// ---------------------------------------------------------------------------
// Design tokens — mirrors CSS variables in globals.css
// Chart libraries (Recharts, TradingView) need JS values; this is the single
// source of truth. Every hex value in the app should come from here or from
// Tailwind utility classes that reference the same CSS variables.
// ---------------------------------------------------------------------------

export const themeColors = {
  background: "#0a0a0f",
  foreground: "#e4e4e7",
  card: "#111118",
  cardHover: "#1a1a24",
  border: "#27272a",
  accent: "#3b82f6",
  accentHover: "#2563eb",
  green: "#22c55e",
  red: "#ef4444",
  yellow: "#eab308",
  muted: "#71717a",
  purple: "#a855f7",
  cyan: "#06b6d4",
  orange: "#f97316",
} as const;

// ---------------------------------------------------------------------------
// Reusable Recharts style objects
// ---------------------------------------------------------------------------

/** Standard axis tick styling for all Recharts axes */
export const chartAxisTick = { fill: themeColors.muted, fontSize: 11 } as const;

/** Standard CartesianGrid props */
export const chartGridProps = {
  strokeDasharray: "3 3",
  stroke: themeColors.border,
} as const;

/** Standard Tooltip contentStyle */
export const chartTooltipStyle = {
  background: themeColors.card,
  border: `1px solid ${themeColors.border}`,
  borderRadius: 8,
  color: themeColors.foreground,
} as const;

/** Standard Tooltip labelStyle */
export const chartLabelStyle = { color: themeColors.muted } as const;

// ---------------------------------------------------------------------------
// Color palettes for multi-series charts (pie, radar, etc.)
// ---------------------------------------------------------------------------

export const seriesColors = [
  themeColors.accent,
  themeColors.green,
  themeColors.purple,
  themeColors.orange,
  themeColors.cyan,
  themeColors.yellow,
] as const;

// ---------------------------------------------------------------------------
// TradingView Lightweight Charts
// ---------------------------------------------------------------------------

export const darkChartOptions: DeepPartial<ChartOptions> = {
  layout: {
    background: { type: ColorType.Solid, color: "transparent" },
    textColor: themeColors.muted,
  },
  grid: {
    vertLines: { color: themeColors.border },
    horzLines: { color: themeColors.border },
  },
  crosshair: {
    vertLine: { color: themeColors.accent, width: 1, style: 2 },
    horzLine: { color: themeColors.accent, width: 1, style: 2 },
  },
  timeScale: {
    borderColor: themeColors.border,
    timeVisible: true,
  },
  rightPriceScale: {
    borderColor: themeColors.border,
  },
};

export const candleColors = {
  upColor: themeColors.green,
  downColor: themeColors.red,
  borderUpColor: themeColors.green,
  borderDownColor: themeColors.red,
  wickUpColor: themeColors.green,
  wickDownColor: themeColors.red,
} as const;

// Legacy alias — use themeColors directly in new code
export const rechartsColors = {
  primary: themeColors.accent,
  green: themeColors.green,
  red: themeColors.red,
  yellow: themeColors.yellow,
  purple: themeColors.purple,
  cyan: themeColors.cyan,
  orange: themeColors.orange,
  grid: themeColors.border,
  text: themeColors.muted,
  background: themeColors.card,
} as const;
