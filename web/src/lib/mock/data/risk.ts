import { registerRoute } from "../router";

// ---------------------------------------------------------------------------
// Module-level mutable state
// ---------------------------------------------------------------------------
let mockRiskSettings = {
  max_position_pct: 2,
  max_sector_exposure_pct: 20,
  daily_loss_limit_pct: 3,
  weekly_drawdown_limit_pct: 5,
  max_open_positions: 10,
  stop_loss_pct: 5,
  trailing_stop_enabled: true,
  trailing_stop_pct: 3,
  max_correlation: 0.7,
};

const mockCircuitBreaker = {
  tripped: false,
  tripped_at: null as string | null,
  reason: null as string | null,
  daily_loss_pct: 1.2,
  threshold_pct: 3.0,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function getLimitsForRegime(regime: string) {
  switch (regime) {
    case "low":
      return {
        max_position_pct: 1.5,
        max_sector_exposure_pct: 15,
        daily_loss_limit_pct: 2,
        weekly_drawdown_limit_pct: 3,
        max_open_positions: 8,
        stop_loss_pct: 3,
        trailing_stop_pct: 2,
        max_correlation: 0.5,
      };
    case "high":
      return {
        max_position_pct: 4,
        max_sector_exposure_pct: 30,
        daily_loss_limit_pct: 5,
        weekly_drawdown_limit_pct: 8,
        max_open_positions: 15,
        stop_loss_pct: 8,
        trailing_stop_pct: 5,
        max_correlation: 0.85,
      };
    default:
      return {
        max_position_pct: mockRiskSettings.max_position_pct,
        max_sector_exposure_pct: mockRiskSettings.max_sector_exposure_pct,
        daily_loss_limit_pct: mockRiskSettings.daily_loss_limit_pct,
        weekly_drawdown_limit_pct: mockRiskSettings.weekly_drawdown_limit_pct,
        max_open_positions: mockRiskSettings.max_open_positions,
        stop_loss_pct: mockRiskSettings.stop_loss_pct,
        trailing_stop_pct: mockRiskSettings.trailing_stop_pct,
        max_correlation: mockRiskSettings.max_correlation,
      };
  }
}

const presets: Record<string, Partial<typeof mockRiskSettings>> = {
  conservative: {
    max_position_pct: 1,
    daily_loss_limit_pct: 1.5,
    weekly_drawdown_limit_pct: 3,
    max_open_positions: 5,
  },
  moderate: {
    max_position_pct: 2,
    daily_loss_limit_pct: 3,
    weekly_drawdown_limit_pct: 5,
    max_open_positions: 10,
  },
  aggressive: {
    max_position_pct: 5,
    daily_loss_limit_pct: 5,
    weekly_drawdown_limit_pct: 8,
    max_open_positions: 15,
  },
  very_aggressive: {
    max_position_pct: 10,
    daily_loss_limit_pct: 8,
    weekly_drawdown_limit_pct: 12,
    max_open_positions: 20,
  },
};

// ---------------------------------------------------------------------------
// POST /api/risk/circuit-breaker/reset  (must come before circuit-breaker GET)
// ---------------------------------------------------------------------------
registerRoute("POST", /^\/api\/risk\/circuit-breaker\/reset$/, () => {
  mockCircuitBreaker.tripped = false;
  mockCircuitBreaker.tripped_at = null;
  mockCircuitBreaker.reason = null;
  return { message: "Circuit breaker reset" };
});

// ---------------------------------------------------------------------------
// GET /api/risk/circuit-breaker
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/risk\/circuit-breaker$/, () => {
  return mockCircuitBreaker;
});

// ---------------------------------------------------------------------------
// GET /api/risk/limits/all  (must come before limits GET)
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/risk\/limits\/all$/, () => {
  return {
    low: getLimitsForRegime("low"),
    medium: getLimitsForRegime("medium"),
    high: getLimitsForRegime("high"),
  };
});

// ---------------------------------------------------------------------------
// GET /api/risk/limits
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/risk\/limits$/, (path) => {
  const queryString = path.split("?")[1] ?? "";
  const params = new URLSearchParams(queryString);
  const regime = params.get("regime") ?? "medium";
  return getLimitsForRegime(regime);
});

// ---------------------------------------------------------------------------
// GET /api/risk/status
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/risk\/status$/, () => {
  return { ...mockRiskSettings, status: "active", regime: "medium" };
});

// ---------------------------------------------------------------------------
// PUT /api/risk/settings
// ---------------------------------------------------------------------------
registerRoute("PUT", /^\/api\/risk\/settings$/, (_path, options) => {
  const body = JSON.parse((options?.body as string) ?? "{}");
  mockRiskSettings = { ...mockRiskSettings, ...body };
  return mockRiskSettings;
});

// ---------------------------------------------------------------------------
// PUT /api/risk/preset
// ---------------------------------------------------------------------------
registerRoute("PUT", /^\/api\/risk\/preset$/, (_path, options) => {
  const body = JSON.parse((options?.body as string) ?? "{}");
  const level: string = body.level ?? "moderate";
  const preset = presets[level];
  if (preset) {
    mockRiskSettings = { ...mockRiskSettings, ...preset };
  }
  return mockRiskSettings;
});

// ---------------------------------------------------------------------------
// GET /api/risk/presets
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/risk\/presets$/, () => {
  return presets;
});

// ---------------------------------------------------------------------------
// GET /api/risk/regime
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/risk\/regime$/, () => {
  return {
    regime: "medium",
    description: "Normal market conditions with moderate volatility",
  };
});

// ---------------------------------------------------------------------------
// GET /api/risk/drawdown
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/risk\/drawdown$/, () => {
  return {
    daily_pct: 1.2,
    daily_limit: mockRiskSettings.daily_loss_limit_pct,
    weekly_pct: 2.8,
    weekly_limit: mockRiskSettings.weekly_drawdown_limit_pct,
    positions_used: 7,
    positions_limit: mockRiskSettings.max_open_positions,
  };
});

// ---------------------------------------------------------------------------
// GET /api/risk/decisions
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/risk\/decisions$/, () => {
  const now = Date.now();
  return [
    {
      id: "rd-1",
      action: "approve",
      symbol: "AAPL",
      reason: "Within risk limits",
      timestamp: new Date(now - 60_000).toISOString(),
    },
    {
      id: "rd-2",
      action: "resize",
      symbol: "NVDA",
      reason: "Position exceeds max size, reduced by 30%",
      timestamp: new Date(now - 120_000).toISOString(),
    },
    {
      id: "rd-3",
      action: "approve",
      symbol: "BTC/USD",
      reason: "Crypto allocation within bounds",
      timestamp: new Date(now - 300_000).toISOString(),
    },
    {
      id: "rd-4",
      action: "veto",
      symbol: "TSLA",
      reason: "Daily loss limit approaching threshold",
      timestamp: new Date(now - 600_000).toISOString(),
    },
    {
      id: "rd-5",
      action: "approve",
      symbol: "MSFT",
      reason: "Low correlation with existing positions",
      timestamp: new Date(now - 900_000).toISOString(),
    },
  ];
});
