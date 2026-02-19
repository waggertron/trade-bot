import { hashString, seededRandom } from "../generators";
import { registerRoute } from "../router";
import { ALL_SYMBOLS, STRATEGY_DESCRIPTIONS, STRATEGY_NAMES, STRATEGY_TYPES } from "./constants";

// ---------------------------------------------------------------------------
// Mutable state
// ---------------------------------------------------------------------------

const mockStrategies = STRATEGY_NAMES.map((name, i) => ({
  name,
  type: STRATEGY_TYPES[name],
  enabled: i < 4, // first 4 enabled
  weight: [0.25, 0.2, 0.15, 0.2, 0.1, 0.1][i],
  description: STRATEGY_DESCRIPTIONS[name],
  total_trades: [145, 98, 67, 203, 54, 178][i],
  win_rate: [58.2, 52.1, 64.8, 55.3, 61.5, 49.7][i],
}));

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ConsensusVote {
  strategy: string;
  symbol: string;
  confidence: number;
  direction: "buy" | "sell" | "hold";
}

interface Signal {
  id: string;
  symbol: string;
  direction: "buy" | "sell" | "hold";
  confidence: number;
  strategy: string;
  reasoning: string;
  timestamp: string;
}

// ---------------------------------------------------------------------------
// GET /api/strategies/ - list all strategies
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/strategies\/?$/, () => {
  return mockStrategies;
});

// ---------------------------------------------------------------------------
// GET /api/strategies/status - strategy status summary
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/strategies\/status$/, () => {
  return {
    active: mockStrategies.filter((s) => s.enabled).length,
    total: mockStrategies.length,
    mode: "paper",
  };
});

// ---------------------------------------------------------------------------
// GET /api/strategies/consensus - consensus votes across strategies
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/strategies\/consensus$/, () => {
  const rng = seededRandom(789);
  const directions: ("buy" | "sell" | "hold")[] = ["buy", "sell", "hold"];
  const votes: ConsensusVote[] = [];

  for (const strategy of STRATEGY_NAMES) {
    // 3 votes per strategy = 18 total
    for (let j = 0; j < 3; j++) {
      const symbolIdx = Math.floor(rng() * ALL_SYMBOLS.length);
      const dirIdx = Math.floor(rng() * 3);
      const confidence = Math.round((0.4 + rng() * 0.55) * 100) / 100;

      votes.push({
        strategy,
        symbol: ALL_SYMBOLS[symbolIdx],
        confidence,
        direction: directions[dirIdx],
      });
    }
  }

  const symbols = [...new Set(votes.map((v) => v.symbol))];

  return { votes, symbols };
});

// ---------------------------------------------------------------------------
// PUT /api/strategies/:name/weight - update strategy weight
// ---------------------------------------------------------------------------
registerRoute("PUT", /^\/api\/strategies\/[^/]+\/weight$/, (path, options) => {
  const parts = path.split("?")[0].split("/");
  const nameIdx = parts.indexOf("strategies") + 1;
  const name = parts[nameIdx];

  const body = JSON.parse((options?.body as string) ?? "{}");
  const strategy = mockStrategies.find((s) => s.name === name);

  if (strategy && body.weight !== undefined) {
    strategy.weight = body.weight;
  }

  return strategy ?? {};
});

// ---------------------------------------------------------------------------
// PUT /api/strategies/:name/enabled - toggle strategy enabled
// ---------------------------------------------------------------------------
registerRoute("PUT", /^\/api\/strategies\/[^/]+\/enabled$/, (path, options) => {
  const parts = path.split("?")[0].split("/");
  const nameIdx = parts.indexOf("strategies") + 1;
  const name = parts[nameIdx];

  const body = JSON.parse((options?.body as string) ?? "{}");
  const strategy = mockStrategies.find((s) => s.name === name);

  if (strategy && body.enabled !== undefined) {
    strategy.enabled = body.enabled;
  }

  return strategy ?? {};
});

// ---------------------------------------------------------------------------
// GET /api/strategies/:name/signals - signals for a strategy
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/strategies\/[^/]+\/signals$/, (path) => {
  const name = path.split("?")[0].split("/").filter(Boolean).at(-2) ?? "";
  const seed = hashString(name);
  const rng = seededRandom(seed);

  const directions: ("buy" | "sell" | "hold")[] = ["buy", "sell", "hold"];
  const reasonings = [
    "Strong momentum detected with rising volume",
    "RSI divergence signals potential reversal",
    "Sentiment score exceeds threshold",
    "ML model confidence above 80%",
    "Moving average crossover confirmed",
    "Support level bounce detected",
    "Breakout above resistance with volume",
    "Mean reversion signal triggered",
    "Correlation breakdown in pair",
    "Trend continuation pattern confirmed",
  ];

  const signals: Signal[] = [];
  const now = Date.now();

  for (let i = 0; i < 10; i++) {
    const symbolIdx = Math.floor(rng() * ALL_SYMBOLS.length);
    const dirIdx = Math.floor(rng() * 3);
    const confidence = Math.round((0.3 + rng() * 0.65) * 100) / 100;
    const reasonIdx = Math.floor(rng() * reasonings.length);
    // Spread over last 48 hours
    const hoursAgo = rng() * 48;
    const timestamp = new Date(now - hoursAgo * 3_600_000).toISOString();

    signals.push({
      id: `sig_${name}_${i}`,
      symbol: ALL_SYMBOLS[symbolIdx],
      direction: directions[dirIdx],
      confidence,
      strategy: name,
      reasoning: reasonings[reasonIdx],
      timestamp,
    });
  }

  return signals;
});

// ---------------------------------------------------------------------------
// GET /api/strategies/:name/performance - performance stats for a strategy
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/strategies\/[^/]+\/performance$/, (path) => {
  const name = path.split("?")[0].split("/").filter(Boolean).at(-2) ?? "";
  const strategy = mockStrategies.find((s) => s.name === name);

  const seed = hashString(`${name}_perf`);
  const rng = seededRandom(seed);

  const totalTrades = strategy?.total_trades ?? 100;
  const winRate = strategy?.win_rate ?? 55;

  const totalPnl = Math.round((rng() * 40000 - 5000) * 100) / 100;
  const avgWin = Math.round((200 + rng() * 800) * 100) / 100;
  const avgLoss = Math.round((-100 - rng() * 500) * 100) / 100;
  const profitFactor = Math.round((1.1 + rng() * 1.5) * 100) / 100;
  const maxConsecutiveLosses = Math.floor(2 + rng() * 6);
  const sharpeRatio = Math.round((0.5 + rng() * 2.0) * 100) / 100;

  return {
    name,
    total_trades: totalTrades,
    win_rate: winRate,
    total_pnl: totalPnl,
    avg_win: avgWin,
    avg_loss: avgLoss,
    profit_factor: profitFactor,
    max_consecutive_losses: maxConsecutiveLosses,
    sharpe_ratio: sharpeRatio,
  };
});

// ---------------------------------------------------------------------------
// GET /api/strategies/:name - single strategy (catch-all, registered LAST)
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/strategies\/[^/]+$/, (path) => {
  const name = path.split("?")[0].split("/").filter(Boolean).at(-1) ?? "";
  const strategy = mockStrategies.find((s) => s.name === name);
  return strategy ?? {};
});
