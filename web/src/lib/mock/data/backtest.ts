import { registerRoute } from "../router";
import { generateEquityCurve } from "../generators";

// ---------------------------------------------------------------------------
// Mutable state
// ---------------------------------------------------------------------------
const mockRuns: Record<string, unknown>[] = [];

// ---------------------------------------------------------------------------
// POST /api/backtest/run  –  launch a new backtest
// ---------------------------------------------------------------------------
registerRoute("POST", /^\/api\/backtest\/run$/, (_path, options) => {
  const config = JSON.parse(options?.body as string ?? "{}");

  const id = `bt-${Date.now()}`;
  const equityCurve = generateEquityCurve(
    250,
    config.initial_capital || 100000,
    0.001,
    0.018,
    Date.now(),
  );
  const finalValue = equityCurve[equityCurve.length - 1].value;
  const startValue = config.initial_capital || 100000;
  const returnPct = ((finalValue - startValue) / startValue) * 100;

  const run = {
    id,
    status: "completed",
    config,
    started_at: new Date().toISOString(),
    result: {
      return_pct: Math.round(returnPct * 100) / 100,
      win_rate: 0.56 + Math.random() * 0.1,
      max_drawdown: -(5 + Math.random() * 8),
      sharpe_ratio: 1.2 + Math.random() * 0.8,
      total_trades: 150 + Math.floor(Math.random() * 200),
      equity_curve: equityCurve.map((p, i) => ({ index: i, value: p.value })),
    },
  };

  mockRuns.push(run);
  return run;
});

// ---------------------------------------------------------------------------
// GET /api/backtest/runs  –  list all backtest runs
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/backtest\/runs$/, () => {
  return mockRuns;
});

// ---------------------------------------------------------------------------
// GET /api/backtest/runs/:id  –  get a single backtest run
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/backtest\/runs\/[^/]+$/, (path) => {
  const match = path.match(/\/api\/backtest\/runs\/([^/]+)/);
  const runId = match?.[1] ?? "";
  return mockRuns.find((r) => r.id === runId) ?? {};
});
