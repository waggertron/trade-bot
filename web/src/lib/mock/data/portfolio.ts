import { generateEquityCurve } from "../generators";
import { registerRoute } from "../router";
import { BASE_PRICES, CRYPTO_SYMBOLS, SECTORS, STOCK_SYMBOLS } from "./constants";

// ---------------------------------------------------------------------------
// Position data
// ---------------------------------------------------------------------------

interface Position {
  symbol: string;
  quantity: string;
  avg_entry_price: string;
  current_price: string;
  market_value: string;
  unrealized_pnl: string;
  asset_type: "stock" | "crypto";
  sector?: string;
}

const positionDefs: {
  symbol: string;
  quantity: number;
  entry: number;
  current: number;
}[] = [
  { symbol: "AAPL", quantity: 150, entry: 185.2, current: BASE_PRICES.AAPL },
  { symbol: "MSFT", quantity: 80, entry: 395.4, current: BASE_PRICES.MSFT },
  { symbol: "GOOGL", quantity: 200, entry: 168.75, current: BASE_PRICES.GOOGL },
  { symbol: "NVDA", quantity: 45, entry: 780.0, current: BASE_PRICES.NVDA },
  { symbol: "TSLA", quantity: 100, entry: 265.3, current: BASE_PRICES.TSLA },
  { symbol: "BTC/USD", quantity: 1.5, entry: 89500, current: BASE_PRICES["BTC/USD"] },
  { symbol: "ETH/USD", quantity: 10, entry: 3050, current: BASE_PRICES["ETH/USD"] },
];

function buildPositions(): Position[] {
  return positionDefs.map((d) => {
    const marketValue = d.quantity * d.current;
    const unrealizedPnl = d.quantity * (d.current - d.entry);
    const isStock = STOCK_SYMBOLS.includes(d.symbol);
    const isCrypto = CRYPTO_SYMBOLS.includes(d.symbol);

    return {
      symbol: d.symbol,
      quantity: d.quantity.toString(),
      avg_entry_price: d.entry.toFixed(2),
      current_price: d.current.toFixed(2),
      market_value: marketValue.toFixed(2),
      unrealized_pnl: unrealizedPnl.toFixed(2),
      asset_type: isCrypto ? "crypto" : "stock",
      ...(isStock || isCrypto ? { sector: SECTORS[d.symbol] } : {}),
    };
  });
}

const positions = buildPositions();

// ---------------------------------------------------------------------------
// Derived totals
// ---------------------------------------------------------------------------

const totalPositionValue = positions.reduce((sum, p) => sum + parseFloat(p.market_value), 0);
const cash = 245320.5;
const totalValue = cash + totalPositionValue;

const totalUnrealizedPnl = positions.reduce((sum, p) => sum + parseFloat(p.unrealized_pnl), 0);

// ---------------------------------------------------------------------------
// Range mapping for equity curve
// ---------------------------------------------------------------------------

const RANGE_DAYS: Record<string, number> = {
  "1D": 1,
  "1W": 7,
  "1M": 30,
  "3M": 90,
  "1Y": 365,
  ALL: 730,
};

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------

// GET /api/portfolio/ - portfolio snapshot
registerRoute("GET", /^\/api\/portfolio\/$/, () => ({
  cash: cash.toFixed(2),
  total_value: totalValue.toFixed(2),
  positions,
}));

// GET /api/portfolio/positions - all positions
registerRoute("GET", /^\/api\/portfolio\/positions$/, () => positions);

// GET /api/portfolio/pnl - PnL summary
registerRoute("GET", /^\/api\/portfolio\/pnl$/, (path: string) => {
  const url = new URL(path, "http://localhost");
  const _period = url.searchParams.get("period") ?? "1M";

  const realizedPnl = 15420.8;
  const totalPnl = realizedPnl + totalUnrealizedPnl;

  return {
    realized_pnl: realizedPnl.toFixed(2),
    unrealized_pnl: totalUnrealizedPnl.toFixed(2),
    total_pnl: totalPnl.toFixed(2),
    win_rate: 62.5,
    total_trades: 184,
    winning_trades: 115,
  };
});

// GET /api/portfolio/equity-curve - equity curve points
registerRoute("GET", /^\/api\/portfolio\/equity-curve$/, (path: string) => {
  const url = new URL(path, "http://localhost");
  const range = url.searchParams.get("range") ?? "1M";
  const days = RANGE_DAYS[range] ?? 30;
  const points = generateEquityCurve(days, 1000000, undefined, undefined, 42);

  return { points };
});

// GET /api/portfolio/allocation - allocation breakdown
registerRoute("GET", /^\/api\/portfolio\/allocation$/, () => {
  // Compute stock / crypto percentages relative to total_value
  const stockValue = positions
    .filter((p) => p.asset_type === "stock")
    .reduce((s, p) => s + parseFloat(p.market_value), 0);
  const cryptoValue = positions
    .filter((p) => p.asset_type === "crypto")
    .reduce((s, p) => s + parseFloat(p.market_value), 0);

  const stockPct = Math.round((stockValue / totalValue) * 1000) / 10;
  const cryptoPct = Math.round((cryptoValue / totalValue) * 1000) / 10;
  const cashPct = Math.round((cash / totalValue) * 1000) / 10;

  // Sector breakdown
  const sectorTotals: Record<string, number> = {};
  for (const p of positions) {
    const sector = SECTORS[p.symbol] ?? "Other";
    sectorTotals[sector] = (sectorTotals[sector] ?? 0) + parseFloat(p.market_value);
  }
  const bySector: Record<string, number> = {};
  for (const [sector, val] of Object.entries(sectorTotals)) {
    bySector[sector] = Math.round((val / totalValue) * 1000) / 10;
  }
  bySector.Cash = cashPct;

  return {
    by_type: { stock: stockPct, crypto: cryptoPct },
    by_sector: bySector,
    cash_pct: cashPct,
  };
});
