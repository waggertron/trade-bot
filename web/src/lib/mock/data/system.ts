import { registerRoute } from "../router";

// ---------------------------------------------------------------------------
// Module-level mutable state
// ---------------------------------------------------------------------------
let mockIsPaused = false;
const startTime = Date.now();

// ---------------------------------------------------------------------------
// GET /api/health  –  health check
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/health$/, () => {
  return { status: "healthy" };
});

// ---------------------------------------------------------------------------
// GET /api/system/status  –  full system status
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/system\/status$/, () => {
  return {
    mode: "paper",
    is_paused: mockIsPaused,
    uptime_seconds: Math.floor((Date.now() - startTime) / 1000),
    strategies_count: 6,
    active_strategies: 4,
    positions_count: 7,
    last_trade: new Date(Date.now() - 180000).toISOString(),
    memory_usage_mb: 245,
    cpu_usage_pct: 12.5,
  };
});

// ---------------------------------------------------------------------------
// POST /api/kill  –  emergency stop
// ---------------------------------------------------------------------------
registerRoute("POST", /^\/api\/kill$/, () => {
  mockIsPaused = true;
  return { status: "killed", message: "Emergency stop activated" };
});

// ---------------------------------------------------------------------------
// POST /api/pause  –  pause trading
// ---------------------------------------------------------------------------
registerRoute("POST", /^\/api\/pause$/, () => {
  mockIsPaused = true;
  return { status: "paused" };
});

// ---------------------------------------------------------------------------
// POST /api/resume  –  resume trading
// ---------------------------------------------------------------------------
registerRoute("POST", /^\/api\/resume$/, () => {
  mockIsPaused = false;
  return { status: "running" };
});
