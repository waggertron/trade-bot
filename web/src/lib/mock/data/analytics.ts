import { registerRoute } from "../router";
import { STRATEGY_NAMES, ALL_SYMBOLS } from "./constants";
import { seededRandom } from "../generators";

// ---------------------------------------------------------------------------
// Strategy attribution data
// ---------------------------------------------------------------------------

interface StrategyAttribution {
  name: string;
  total_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  max_consecutive_losses: number;
}

const strategyData: Record<string, StrategyAttribution> = {
  momentum_breakout: {
    name: "momentum_breakout",
    total_trades: 145,
    win_rate: 0.582,
    total_pnl: 12450,
    avg_win: 280,
    avg_loss: -195,
    profit_factor: 1.67,
    max_consecutive_losses: 5,
  },
  mean_reversion: {
    name: "mean_reversion",
    total_trades: 98,
    win_rate: 0.521,
    total_pnl: 4230,
    avg_win: 210,
    avg_loss: -180,
    profit_factor: 1.21,
    max_consecutive_losses: 7,
  },
  sentiment_alpha: {
    name: "sentiment_alpha",
    total_trades: 67,
    win_rate: 0.648,
    total_pnl: 8920,
    avg_win: 340,
    avg_loss: -220,
    profit_factor: 2.13,
    max_consecutive_losses: 3,
  },
  ml_ensemble: {
    name: "ml_ensemble",
    total_trades: 203,
    win_rate: 0.553,
    total_pnl: 15680,
    avg_win: 195,
    avg_loss: -155,
    profit_factor: 1.42,
    max_consecutive_losses: 6,
  },
  pairs_trading: {
    name: "pairs_trading",
    total_trades: 54,
    win_rate: 0.615,
    total_pnl: -2140,
    avg_win: 180,
    avg_loss: -320,
    profit_factor: 0.87,
    max_consecutive_losses: 8,
  },
  trend_following: {
    name: "trend_following",
    total_trades: 178,
    win_rate: 0.497,
    total_pnl: 3260,
    avg_win: 245,
    avg_loss: -200,
    profit_factor: 1.15,
    max_consecutive_losses: 9,
  },
};

const totalPnl = Object.values(strategyData).reduce(
  (sum, s) => sum + s.total_pnl,
  0,
);

// ---------------------------------------------------------------------------
// Correlation matrix
// ---------------------------------------------------------------------------

// First 7 symbols: AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA, META
const correlationSymbols = ALL_SYMBOLS.slice(0, 7);

// Upper-triangle values (row-major, excluding diagonal)
// Order: AAPL(0), MSFT(1), GOOGL(2), AMZN(3), TSLA(4), NVDA(5), META(6)
const upperTriangle: Record<string, number> = {
  "0-1": 0.82, // AAPL-MSFT
  "0-2": 0.78, // AAPL-GOOGL
  "0-3": 0.62, // AAPL-AMZN
  "0-4": 0.42, // AAPL-TSLA
  "0-5": 0.75, // AAPL-NVDA
  "0-6": 0.72, // AAPL-META
  "1-2": 0.80, // MSFT-GOOGL
  "1-3": 0.65, // MSFT-AMZN
  "1-4": 0.38, // MSFT-TSLA
  "1-5": 0.79, // MSFT-NVDA
  "1-6": 0.74, // MSFT-META
  "2-3": 0.68, // GOOGL-AMZN
  "2-4": 0.45, // GOOGL-TSLA
  "2-5": 0.76, // GOOGL-NVDA
  "2-6": 0.77, // GOOGL-META
  "3-4": 0.48, // AMZN-TSLA
  "3-5": 0.58, // AMZN-NVDA
  "3-6": 0.55, // AMZN-META
  "4-5": 0.43, // TSLA-NVDA
  "4-6": 0.35, // TSLA-META
  "5-6": 0.85, // NVDA-META
};

function buildCorrelationMatrix(): number[][] {
  const n = correlationSymbols.length;
  const matrix: number[][] = Array.from({ length: n }, () =>
    Array(n).fill(0),
  );

  for (let i = 0; i < n; i++) {
    matrix[i][i] = 1.0;
    for (let j = i + 1; j < n; j++) {
      const val = upperTriangle[`${i}-${j}`] ?? 0.5;
      matrix[i][j] = val;
      matrix[j][i] = val;
    }
  }

  return matrix;
}

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------

// GET /api/analytics/attribution - strategy attribution report
registerRoute("GET", /^\/api\/analytics\/attribution$/, () => ({
  strategies: strategyData,
  total_pnl: totalPnl,
  best_strategy: "ml_ensemble",
  worst_strategy: "pairs_trading",
}));

// GET /api/analytics/monte-carlo - Monte Carlo simulation results
registerRoute("GET", /^\/api\/analytics\/monte-carlo$/, () => ({
  actual_final_value: 1042400,
  percentile: 67,
  median_simulated: 1028500,
  p5_simulated: 945200,
  p95_simulated: 1135800,
  worst_drawdown_p95: 0.128,
  n_simulations: 10000,
}));

// GET /api/analytics/drawdown - drawdown time-series
registerRoute("GET", /^\/api\/analytics\/drawdown$/, () => {
  const rng = seededRandom(321);
  const points: { index: number; drawdown_pct: number; value: number }[] = [];
  let value = 1000000;
  let peak = value;
  let drawdownPct = 0;

  for (let i = 0; i < 100; i++) {
    // Slowly increase value with noise
    const dailyReturn = 0.001 + (rng() - 0.52) * 0.025;
    value *= 1 + dailyReturn;

    // Track peak for drawdown calculation
    if (value > peak) {
      peak = value;
    }
    drawdownPct = ((peak - value) / peak) * 100;

    // Clamp to realistic range (0 to ~12%)
    drawdownPct = Math.min(drawdownPct, 12);

    points.push({
      index: i,
      drawdown_pct: Math.round(drawdownPct * 1000) / 1000,
      value: Math.round(value * 100) / 100,
    });
  }

  return { points };
});

// GET /api/analytics/correlation - symbol correlation matrix
registerRoute("GET", /^\/api\/analytics\/correlation$/, () => ({
  symbols: correlationSymbols,
  matrix: buildCorrelationMatrix(),
}));
