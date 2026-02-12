import { type DeepPartial, type ChartOptions, ColorType } from "lightweight-charts";

// ---------------------------------------------------------------------------
// Design tokens — reads CSS variables from globals.css at runtime.
// globals.css is the single source of truth for all color values.
// Chart libraries (Recharts, TradingView) need JS values; this module
// resolves them from CSS custom properties so nothing is duplicated.
// ---------------------------------------------------------------------------

function cssVar(name: string): string {
  if (typeof window === "undefined") return "";
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Read a CSS variable, returning a fallback during SSR */
function token(name: string, fallback: string): string {
  const val = cssVar(name);
  return val || fallback;
}

// Eagerly-resolved tokens for chart libraries that need plain strings.
// Fallbacks match globals.css so SSR / static builds still look correct.
export const themeColors = {
  get background() { return token("--background", "#0a0a0f"); },
  get foreground() { return token("--foreground", "#f0f0f3"); },
  get card()       { return token("--card", "rgba(17, 17, 24, 0.65)"); },
  get cardHover()  { return token("--card-hover", "rgba(30, 30, 42, 0.7)"); },
  get border()     { return token("--border", "rgba(55, 55, 68, 0.6)"); },
  get accent()     { return token("--accent", "#3b82f6"); },
  get accentHover(){ return token("--accent-hover", "#2563eb"); },
  get green()      { return token("--green", "#22c55e"); },
  get red()        { return token("--red", "#ef4444"); },
  get yellow()     { return token("--yellow", "#eab308"); },
  get muted()      { return token("--muted", "#9ca3af"); },
  get purple()     { return token("--purple", "#a855f7"); },
  get cyan()       { return token("--cyan", "#06b6d4"); },
  get orange()     { return token("--orange", "#f97316"); },
} as const;

/** Build an rgba() string from a CSS `--*-rgb` channel variable with dynamic opacity */
export function themeRgba(channelVar: string, opacity: number): string {
  const channels = cssVar(channelVar) || "128, 128, 128";
  return `rgba(${channels}, ${opacity})`;
}

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
