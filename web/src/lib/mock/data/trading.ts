import { registerRoute } from "../router";
import { generateOHLC, generateSparkline, hashString } from "../generators";
import { BASE_PRICES, ALL_SYMBOLS, INTERVAL_MS, STRATEGY_NAMES } from "./constants";

// ---------------------------------------------------------------------------
// Order shape
// ---------------------------------------------------------------------------
interface Order {
  id: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: string;
  limit_price?: string;
  status: "open" | "filled" | "cancelled";
  created_at: string;
}

// ---------------------------------------------------------------------------
// Module-level mutable state: seed orders
// ---------------------------------------------------------------------------
const mockOrders: Order[] = [
  {
    id: "ord_seed_1",
    symbol: "AAPL",
    side: "buy",
    order_type: "limit",
    quantity: "10",
    limit_price: "195.00",
    status: "open",
    created_at: new Date(Date.now() - 3_600_000).toISOString(),
  },
  {
    id: "ord_seed_2",
    symbol: "ETH/USD",
    side: "sell",
    order_type: "limit",
    quantity: "5",
    limit_price: "3400.00",
    status: "open",
    created_at: new Date(Date.now() - 1_800_000).toISOString(),
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
let orderCounter = 100;

function nextOrderId(): string {
  return `ord_${++orderCounter}`;
}

const CRYPTO_SYMBOLS = new Set(["BTC/USD", "ETH/USD", "SOL/USD"]);

// ---------------------------------------------------------------------------
// GET /api/trading/prices  –  current prices for all symbols
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/trading\/prices$/, () => {
  const prices: Record<string, string> = {};
  for (const symbol of ALL_SYMBOLS) {
    const base = BASE_PRICES[symbol];
    const variation = 1 + (Math.random() - 0.5) * 0.01; // +/- 0.5%
    prices[symbol] = (base * variation).toFixed(2);
  }
  return prices;
});

// ---------------------------------------------------------------------------
// GET /api/trading/orders  –  list all orders
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/trading\/orders$/, () => {
  return mockOrders;
});

// ---------------------------------------------------------------------------
// POST /api/trading/order  –  place a new order
// ---------------------------------------------------------------------------
registerRoute("POST", /^\/api\/trading\/order$/, (_path, options) => {
  const body = JSON.parse(options?.body as string ?? "{}");
  const symbol: string = body.symbol ?? "AAPL";
  const side: string = body.side ?? "buy";
  const quantity: string = String(body.quantity ?? "1");
  const orderType: string = body.order_type ?? "market";
  const limitPrice: string | undefined = body.limit_price ? String(body.limit_price) : undefined;

  const id = nextOrderId();
  const basePrice = BASE_PRICES[symbol] ?? 100;
  const slippage = 1 + (Math.random() - 0.5) * 0.002; // +/- 0.1% slippage
  const fillPrice = (basePrice * slippage).toFixed(2);
  const timestamp = new Date().toISOString();

  const order: Order = {
    id,
    symbol,
    side,
    order_type: orderType,
    quantity,
    ...(limitPrice ? { limit_price: limitPrice } : {}),
    status: orderType === "market" ? "filled" : "open",
    created_at: timestamp,
  };

  mockOrders.push(order);

  return {
    fill: {
      id,
      symbol,
      side,
      quantity,
      fill_price: fillPrice,
      timestamp,
    },
  };
});

// ---------------------------------------------------------------------------
// DELETE /api/trading/orders/:id  –  cancel a single order
// ---------------------------------------------------------------------------
registerRoute("DELETE", /^\/api\/trading\/orders\/([^/]+)$/, (path) => {
  const match = path.match(/\/api\/trading\/orders\/([^/]+)/);
  const orderId = match?.[1] ?? "";

  const order = mockOrders.find((o) => o.id === orderId);
  if (order && order.status === "open") {
    order.status = "cancelled";
  }

  return { cancelled: true };
});

// ---------------------------------------------------------------------------
// POST /api/trading/cancel-all  –  cancel all open orders
// ---------------------------------------------------------------------------
registerRoute("POST", /^\/api\/trading\/cancel-all$/, () => {
  let count = 0;
  for (const order of mockOrders) {
    if (order.status === "open") {
      order.status = "cancelled";
      count++;
    }
  }
  return { cancelled_count: count };
});

// ---------------------------------------------------------------------------
// GET /api/market/ohlc/:symbol  –  OHLCV bars
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/market\/ohlc\/.+$/, (path) => {
  const [pathOnly, queryString] = path.split("?");
  const symbolMatch = pathOnly.match(/\/api\/market\/ohlc\/(.+)/);
  const symbol = decodeURIComponent(symbolMatch?.[1] ?? "AAPL");

  const params = new URLSearchParams(queryString ?? "");
  const interval = params.get("interval") ?? "1h";
  const limit = parseInt(params.get("limit") ?? "100", 10);

  const basePrice = BASE_PRICES[symbol] ?? 100;
  const volatility = CRYPTO_SYMBOLS.has(symbol) ? 0.03 : 0.015;
  const intervalMs = INTERVAL_MS[interval] ?? INTERVAL_MS["1h"];
  const seed = hashString(symbol + interval);

  return generateOHLC(limit, basePrice, volatility, intervalMs, seed);
});

// ---------------------------------------------------------------------------
// GET /api/market/prices  –  same as trading/prices
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/market\/prices$/, () => {
  const prices: Record<string, string> = {};
  for (const symbol of ALL_SYMBOLS) {
    const base = BASE_PRICES[symbol];
    const variation = 1 + (Math.random() - 0.5) * 0.01; // +/- 0.5%
    prices[symbol] = (base * variation).toFixed(2);
  }
  return prices;
});

// ---------------------------------------------------------------------------
// GET /api/market/sparklines  –  sparkline data for all symbols
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/market\/sparklines$/, () => {
  const result: Record<string, { prices: number[]; current: number; change_pct: number }> = {};

  for (const symbol of ALL_SYMBOLS) {
    const base = BASE_PRICES[symbol];
    const seed = hashString(symbol);
    // Deterministic changePct between -3% and +5% per symbol
    const changePct = -3 + ((seed % 1000) / 1000) * 8;
    const current = Math.round(base * (1 + changePct / 100) * 100) / 100;
    const prices = generateSparkline(30, current, changePct, seed);

    result[symbol] = {
      prices,
      current,
      change_pct: Math.round(changePct * 100) / 100,
    };
  }

  return result;
});
