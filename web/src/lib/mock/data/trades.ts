import { registerRoute } from "../router";
import { seededRandom } from "../generators";
import { ALL_SYMBOLS, STRATEGY_NAMES, BASE_PRICES } from "./constants";

// ---------------------------------------------------------------------------
// Reasoning strings for signals
// ---------------------------------------------------------------------------

const SIGNAL_REASONS = [
  "RSI divergence detected on 4h chart with volume confirmation",
  "Price breaking above 200-day SMA with increasing momentum",
  "Sentiment score turned positive after earnings beat",
  "Mean reversion signal: price 2.1 std devs below 20-day mean",
  "ML ensemble predicts 72% probability of upward move",
  "MACD histogram crossover with bullish divergence on daily",
  "Order flow imbalance detected at key support level",
  "Bollinger Band squeeze breakout with above-average volume",
  "Pairs spread widened beyond 2.5 sigma threshold",
  "News sentiment shift: 3 consecutive positive catalysts",
  "Fibonacci retracement holding at 61.8% level with hammer candle",
  "Institutional accumulation detected via dark pool prints",
  "Volatility contraction pattern preceding directional move",
  "Cross-asset momentum confirming sector rotation signal",
];

// ---------------------------------------------------------------------------
// Mock trade generation (200 trades)
// ---------------------------------------------------------------------------

interface Trade {
  id: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: string;
  price: string;
  commission: string;
  strategy: string;
  paper: boolean;
  timestamp: string;
}

const CRYPTO_SYMBOLS = ["BTC/USD", "ETH/USD", "SOL/USD"];

function generateTrades(): Trade[] {
  const rng = seededRandom(123);
  const trades: Trade[] = [];
  const now = Date.now();
  const thirtyDaysMs = 30 * 24 * 60 * 60 * 1000;

  for (let i = 0; i < 200; i++) {
    const idx = Math.floor(rng() * ALL_SYMBOLS.length);
    const symbol = ALL_SYMBOLS[idx];
    const isCrypto = CRYPTO_SYMBOLS.includes(symbol);

    const side: "buy" | "sell" = rng() < 0.5 ? "buy" : "sell";

    // Stocks: 10-500 shares, Crypto: 0.1-10 units
    const quantity = isCrypto
      ? (0.1 + rng() * 9.9).toFixed(4)
      : Math.floor(10 + rng() * 491).toString();

    // Base price with +/-5% variation
    const basePrice = BASE_PRICES[symbol];
    const variation = (rng() - 0.5) * 0.1 * basePrice;
    const price = (basePrice + variation).toFixed(2);

    const commission = (0.5 + rng() * 4.5).toFixed(2);

    const strategyIdx = Math.floor(rng() * STRATEGY_NAMES.length);
    const strategy = STRATEGY_NAMES[strategyIdx];

    // Spread timestamps over the last 30 days
    const timeOffset = rng() * thirtyDaysMs;
    const timestamp = new Date(now - timeOffset).toISOString();

    const padded = String(i + 1).padStart(3, "0");
    trades.push({
      id: `trade-${padded}`,
      symbol,
      side,
      quantity,
      price,
      commission,
      strategy,
      paper: true,
      timestamp,
    });
  }

  // Sort newest first
  trades.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  return trades;
}

const mockTrades = generateTrades();

// ---------------------------------------------------------------------------
// Mock signal generation (50 signals)
// ---------------------------------------------------------------------------

interface Signal {
  id: string;
  symbol: string;
  direction: "buy" | "sell" | "hold";
  confidence: number;
  strategy: string;
  reasoning: string;
  timestamp: string;
}

function generateSignals(): Signal[] {
  const rng = seededRandom(456);
  const signals: Signal[] = [];
  const now = Date.now();
  const twentyFourHoursMs = 24 * 60 * 60 * 1000;

  const directions: ("buy" | "sell" | "hold")[] = ["buy", "sell", "hold"];

  for (let i = 0; i < 50; i++) {
    const symbolIdx = Math.floor(rng() * ALL_SYMBOLS.length);
    const symbol = ALL_SYMBOLS[symbolIdx];

    const dirIdx = Math.floor(rng() * directions.length);
    const direction = directions[dirIdx];

    // Confidence between 0.3 and 0.95
    const confidence = Math.round((0.3 + rng() * 0.65) * 100) / 100;

    const strategyIdx = Math.floor(rng() * STRATEGY_NAMES.length);
    const strategy = STRATEGY_NAMES[strategyIdx];

    const reasonIdx = Math.floor(rng() * SIGNAL_REASONS.length);
    const reasoning = SIGNAL_REASONS[reasonIdx];

    // Spread timestamps over the last 24 hours
    const timeOffset = rng() * twentyFourHoursMs;
    const timestamp = new Date(now - timeOffset).toISOString();

    const padded = String(i + 1).padStart(3, "0");
    signals.push({
      id: `sig-${padded}`,
      symbol,
      direction,
      confidence,
      strategy,
      reasoning,
      timestamp,
    });
  }

  // Sort newest first
  signals.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  return signals;
}

const mockSignals = generateSignals();

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------

// GET /api/trades/ - paginated trade list
registerRoute("GET", /^\/api\/trades\/?$/, (path: string) => {
  const qs = path.includes("?") ? path.split("?")[1] : "";
  const params = new URLSearchParams(qs);

  const limit = parseInt(params.get("limit") ?? "20", 10);
  const offset = parseInt(params.get("offset") ?? "0", 10);
  const strategyFilter = params.get("strategy");
  const symbolFilter = params.get("symbol");

  let filtered = mockTrades;

  if (strategyFilter) {
    filtered = filtered.filter((t) => t.strategy === strategyFilter);
  }
  if (symbolFilter) {
    filtered = filtered.filter((t) => t.symbol === symbolFilter);
  }

  const sliced = filtered.slice(offset, offset + limit);

  return sliced;
});

// GET /api/trades/:id - single trade by id
registerRoute("GET", /^\/api\/trades\/[^/]+$/, (path: string) => {
  const pathOnly = path.split("?")[0];
  const segments = pathOnly.split("/");
  const tradeId = segments[segments.length - 1];
  const trade = mockTrades.find((t) => t.id === tradeId);

  return trade ?? { error: "Trade not found", id: tradeId };
});

// GET /api/signals/ - signals list
registerRoute("GET", /^\/api\/signals\/?$/, (path: string) => {
  const qs = path.includes("?") ? path.split("?")[1] : "";
  const params = new URLSearchParams(qs);

  const limit = parseInt(params.get("limit") ?? "50", 10);
  const strategyFilter = params.get("strategy");
  const symbolFilter = params.get("symbol");

  let filtered = mockSignals;

  if (strategyFilter) {
    filtered = filtered.filter((s) => s.strategy === strategyFilter);
  }
  if (symbolFilter) {
    filtered = filtered.filter((s) => s.symbol === symbolFilter);
  }

  return filtered.slice(0, limit);
});

// GET /api/signals/latest - 10 most recent signals
registerRoute("GET", /^\/api\/signals\/latest$/, () => {
  return mockSignals.slice(0, 10);
});
