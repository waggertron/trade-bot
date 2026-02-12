import { registerRoute } from "../router";
import { STOCK_SYMBOLS, CRYPTO_SYMBOLS } from "./constants";

// ---------------------------------------------------------------------------
// Module-level mutable state
// ---------------------------------------------------------------------------
let mockMode = "paper";
let mockSymbols = {
  stocks: [...STOCK_SYMBOLS],
  crypto: [...CRYPTO_SYMBOLS],
};

// ---------------------------------------------------------------------------
// GET /api/config/mode  –  current trading mode
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/config\/mode$/, () => {
  return { mode: mockMode };
});

// ---------------------------------------------------------------------------
// PUT /api/config/mode  –  update trading mode
// ---------------------------------------------------------------------------
registerRoute("PUT", /^\/api\/config\/mode$/, (_path, options) => {
  const body = JSON.parse(options?.body as string ?? "{}");
  mockMode = body.mode ?? mockMode;
  return { mode: mockMode };
});

// ---------------------------------------------------------------------------
// GET /api/config/symbols  –  configured symbols
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/config\/symbols$/, () => {
  return mockSymbols;
});

// ---------------------------------------------------------------------------
// PUT /api/config/symbols  –  update configured symbols
// ---------------------------------------------------------------------------
registerRoute("PUT", /^\/api\/config\/symbols$/, (_path, options) => {
  const body = JSON.parse(options?.body as string ?? "{}");
  mockSymbols = body;
  return mockSymbols;
});

// ---------------------------------------------------------------------------
// GET /api/config/  –  full configuration
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/config\/?$/, () => {
  return {
    mode: mockMode,
    symbols: mockSymbols,
    risk: { max_position_pct: 2, daily_loss_limit_pct: 3 },
    exchange: { name: "alpaca", paper: mockMode === "paper" },
    data_providers: ["polygon", "coinbase"],
    version: "1.0.0",
  };
});
