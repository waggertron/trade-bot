import { z } from "zod";
import { getMockResponse, MOCK_ENABLED } from "./mock";
import {
  AllocationSchema,
  AuthResponseSchema,
  AttributionSchema,
  BacktestRunSchema,
  CancelAllResultSchema,
  CancelResultSchema,
  CircuitBreakerSchema,
  ConfigSchema,
  ConsensusVotesSchema,
  CorrelationSchema,
  DrawdownSeriesSchema,
  DrawdownStatusSchema,
  EquityCurveSchema,
  FeatureCatalogSchema,
  FeatureImportanceSchema,
  FeatureStatusSchema,
  HealthStatusSchema,
  LoginResponseSchema,
  MarketPricesSchema,
  MLModelSchema,
  MonteCarloSchema,
  NewsArticleSchema,
  NewsStatusSchema,
  OHLCBarSchema,
  OrderSchema,
  PlaceOrderResponseSchema,
  PnLSummarySchema,
  PortfolioSchema,
  PositionSchema,
  PredictionsSchema,
  RefreshResponseSchema,
  RiskDecisionSchema,
  RiskPresetsSchema,
  RiskSettingsSchema,
  RiskStatusSchema,
  SentimentAggregateSchema,
  SentimentTrendSchema,
  SignalSchema,
  SimulationRunSchema,
  SparklineMapSchema,
  StrategyInfoSchema,
  StrategyStatsSchema,
  StrategyStatusSchema,
  SymbolsConfigSchema,
  SystemStatusSchema,
  TradeModeSchema,
  TradeSchema,
  TradingPricesSchema,
  UserSchema,
} from "./schemas";

const API_BASE = "";

function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function csrfHeaders(method?: string): Record<string, string> {
  // Only include CSRF token for state-changing requests
  if (!method || method === "GET" || method === "HEAD" || method === "OPTIONS") return {};
  const token = getCsrfToken();
  return token ? { "X-CSRF-Token": token } : {};
}

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  if (MOCK_ENABLED) return getMockResponse<T>(path, options);
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...csrfHeaders(options?.method),
      ...options?.headers,
    },
  });

  // Auto-refresh on 401
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      // Retry — cookie is now refreshed
      const retry = await fetch(url, {
        ...options,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...csrfHeaders(options?.method),
          ...options?.headers,
        },
      });
      if (!retry.ok) {
        throw new Error(`API error ${retry.status}: ${retry.statusText}`);
      }
      return retry.json();
    }
    // Refresh failed — redirect to login
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expired");
  }

  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

async function tryRefreshToken(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function fetchAndParse<T>(
  path: string,
  schema: z.ZodType<T>,
  options?: RequestInit,
): Promise<T> {
  const data = await fetchAPI<unknown>(path, options);
  return schema.parse(data);
}

// ---------------------------------------------------------------------------
// Auth (no auth header needed for these — they create/validate tokens)
// ---------------------------------------------------------------------------
export const authRegister = (input: { email: string; password: string; name: string }) =>
  fetchAndParse("/api/auth/register", AuthResponseSchema, {
    method: "POST",
    body: JSON.stringify(input),
  });

export const authLogin = (input: { email: string; password: string }) =>
  fetchAndParse("/api/auth/login", LoginResponseSchema, {
    method: "POST",
    body: JSON.stringify(input),
  });

export const authRefresh = () =>
  fetchAndParse("/api/auth/refresh", RefreshResponseSchema, {
    method: "POST",
  });

export const authLogout = () =>
  fetchAPI<{ detail: string }>("/api/auth/logout", { method: "POST" });

export const authMe = () => fetchAndParse("/api/auth/me", UserSchema);

// ---------------------------------------------------------------------------
// Inline schemas for endpoints that don't fit a named domain schema exactly
// ---------------------------------------------------------------------------
const RegimeSchema = z.object({ regime: z.string(), description: z.string() }).passthrough();
const MessageSchema = z.object({ message: z.string() }).passthrough();
const StatusResponseSchema = z.object({ status: z.string() }).passthrough();
const AllRiskLimitsSchema = z.record(z.string(), RiskSettingsSchema);

// ---------------------------------------------------------------------------
// Portfolio
// ---------------------------------------------------------------------------
export const getPortfolio = () => fetchAndParse("/api/portfolio/", PortfolioSchema);
export const getPositions = () =>
  fetchAndParse("/api/portfolio/positions", z.array(PositionSchema));
export const getPnL = (period = "30d") =>
  fetchAndParse(`/api/portfolio/pnl?period=${period}`, PnLSummarySchema);
export const getEquityCurve = (range = "1M") =>
  fetchAndParse(`/api/portfolio/equity-curve?range=${range}`, EquityCurveSchema);
export const getAllocation = () => fetchAndParse("/api/portfolio/allocation", AllocationSchema);

// ---------------------------------------------------------------------------
// Trading
// ---------------------------------------------------------------------------
export const placeOrder = (order: {
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  limit_price?: number;
}) =>
  fetchAndParse("/api/trading/order", PlaceOrderResponseSchema, {
    method: "POST",
    body: JSON.stringify(order),
  });
export const getOrders = () => fetchAndParse("/api/trading/orders", z.array(OrderSchema));
export const cancelOrder = (id: string) =>
  fetchAndParse(`/api/trading/orders/${id}`, CancelResultSchema, { method: "DELETE" });
export const cancelAllOrders = () =>
  fetchAndParse("/api/trading/cancel-all", CancelAllResultSchema, { method: "POST" });
export const getTradingPrices = () => fetchAndParse("/api/trading/prices", TradingPricesSchema);

// ---------------------------------------------------------------------------
// Trades
// ---------------------------------------------------------------------------
export const getTrades = (params?: {
  strategy?: string;
  symbol?: string;
  limit?: number;
  offset?: number;
}) => {
  const sp = new URLSearchParams();
  if (params?.strategy) sp.set("strategy", params.strategy);
  if (params?.symbol) sp.set("symbol", params.symbol);
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  return fetchAndParse(`/api/trades/?${sp}`, z.array(TradeSchema));
};
export const getTrade = (id: string) => fetchAndParse(`/api/trades/${id}`, TradeSchema);

// ---------------------------------------------------------------------------
// Signals
// ---------------------------------------------------------------------------
export const getSignals = (params?: { limit?: number; strategy?: string; symbol?: string }) => {
  const sp = new URLSearchParams();
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.strategy) sp.set("strategy", params.strategy);
  if (params?.symbol) sp.set("symbol", params.symbol);
  return fetchAndParse(`/api/signals/?${sp}`, z.array(SignalSchema));
};
export const getLatestSignals = () => fetchAndParse("/api/signals/latest", z.array(SignalSchema));

// ---------------------------------------------------------------------------
// Strategies
// ---------------------------------------------------------------------------
export const getStrategies = () => fetchAndParse("/api/strategies/", z.array(StrategyInfoSchema));
export const getStrategyStatus = () =>
  fetchAndParse("/api/strategies/status", StrategyStatusSchema);
export const getStrategy = (name: string) =>
  fetchAndParse(`/api/strategies/${name}`, StrategyInfoSchema);
export const updateStrategyWeight = (name: string, weight: number) =>
  fetchAndParse(`/api/strategies/${name}/weight`, StrategyInfoSchema, {
    method: "PUT",
    body: JSON.stringify({ weight }),
  });
export const updateStrategyEnabled = (name: string, enabled: boolean) =>
  fetchAndParse(`/api/strategies/${name}/enabled`, StrategyInfoSchema, {
    method: "PUT",
    body: JSON.stringify({ enabled }),
  });
export const getConsensus = () => fetchAndParse("/api/strategies/consensus", ConsensusVotesSchema);
export const getStrategySignals = (name: string) =>
  fetchAndParse(`/api/strategies/${name}/signals`, z.array(SignalSchema));
export const getStrategyPerformance = (name: string) =>
  fetchAndParse(`/api/strategies/${name}/performance`, StrategyStatsSchema);

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------
export const getAttribution = () => fetchAndParse("/api/analytics/attribution", AttributionSchema);
export const getMonteCarlo = () => fetchAndParse("/api/analytics/monte-carlo", MonteCarloSchema);
export const getDrawdown = () => fetchAndParse("/api/analytics/drawdown", DrawdownSeriesSchema);
export const getCorrelation = () => fetchAndParse("/api/analytics/correlation", CorrelationSchema);

// ---------------------------------------------------------------------------
// Risk
// ---------------------------------------------------------------------------
export const getRiskStatus = () => fetchAndParse("/api/risk/status", RiskStatusSchema);
export const getRiskLimits = (regime?: string) =>
  fetchAndParse(`/api/risk/limits?regime=${regime || "medium"}`, RiskSettingsSchema);
export const getAllRiskLimits = () => fetchAndParse("/api/risk/limits/all", AllRiskLimitsSchema);
export const updateRiskSettings = (settings: Record<string, unknown>) =>
  fetchAndParse("/api/risk/settings", RiskSettingsSchema, {
    method: "PUT",
    body: JSON.stringify(settings),
  });
export const applyRiskPreset = (level: string) =>
  fetchAndParse("/api/risk/preset", RiskSettingsSchema, {
    method: "PUT",
    body: JSON.stringify({ level }),
  });
export const getRiskPresets = () => fetchAndParse("/api/risk/presets", RiskPresetsSchema);
export const getCurrentRegime = () => fetchAndParse("/api/risk/regime", RegimeSchema);
export const getDrawdownStatus = () => fetchAndParse("/api/risk/drawdown", DrawdownStatusSchema);
export const getCircuitBreaker = () =>
  fetchAndParse("/api/risk/circuit-breaker", CircuitBreakerSchema);
export const resetCircuitBreaker = () =>
  fetchAndParse("/api/risk/circuit-breaker/reset", MessageSchema, { method: "POST" });
export const getRiskDecisions = () =>
  fetchAndParse("/api/risk/decisions", z.array(RiskDecisionSchema));

// ---------------------------------------------------------------------------
// Backtest
// ---------------------------------------------------------------------------
export const runBacktest = (config: {
  start_date: string;
  end_date: string;
  strategies: string[];
  symbols: string[];
  initial_capital: number;
}) =>
  fetchAndParse("/api/backtest/run", BacktestRunSchema, {
    method: "POST",
    body: JSON.stringify(config),
  });
export const getBacktestRuns = () =>
  fetchAndParse("/api/backtest/runs", z.array(BacktestRunSchema));
export const getBacktestRun = (id: string) =>
  fetchAndParse(`/api/backtest/runs/${id}`, BacktestRunSchema);

// ---------------------------------------------------------------------------
// News & Sentiment
// ---------------------------------------------------------------------------
export const getNewsStatus = () => fetchAndParse("/api/news/status", NewsStatusSchema);
export const getNewsFeeds = () => fetchAndParse("/api/news/feeds", NewsStatusSchema);
export const getNewsArticles = (params?: { symbol?: string; source?: string; limit?: number }) => {
  const sp = new URLSearchParams();
  if (params?.symbol) sp.set("symbol", params.symbol);
  if (params?.source) sp.set("source", params.source);
  if (params?.limit) sp.set("limit", String(params.limit));
  return fetchAndParse(`/api/news/articles?${sp}`, z.array(NewsArticleSchema));
};
export const getSentimentAggregate = () =>
  fetchAndParse("/api/sentiment/aggregate", SentimentAggregateSchema);
export const getSentimentTrend = (symbol: string, period = "7d") =>
  fetchAndParse(`/api/sentiment/trend?symbol=${symbol}&period=${period}`, SentimentTrendSchema);

// ---------------------------------------------------------------------------
// ML & Features
// ---------------------------------------------------------------------------
export const getFeatureCatalog = () => fetchAndParse("/api/features/catalog", FeatureCatalogSchema);
export const getFeatureStatus = () => fetchAndParse("/api/features/status", FeatureStatusSchema);
export const getMLModels = () => fetchAndParse("/api/ml/models", z.array(MLModelSchema));
export const getModelImportance = (name: string) =>
  fetchAndParse(`/api/ml/models/${name}/importance`, FeatureImportanceSchema);
export const triggerTraining = () =>
  fetchAndParse("/api/ml/train", StatusResponseSchema, { method: "POST" });
export const getPredictions = () => fetchAndParse("/api/ml/predictions", PredictionsSchema);

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
export const getConfig = () => fetchAndParse("/api/config/", ConfigSchema);
export const getMode = () => fetchAndParse("/api/config/mode", TradeModeSchema);
export const setMode = (mode: string) =>
  fetchAndParse("/api/config/mode", TradeModeSchema, {
    method: "PUT",
    body: JSON.stringify({ mode }),
  });
export const getSymbols = () => fetchAndParse("/api/config/symbols", SymbolsConfigSchema);
export const updateSymbols = (symbols: { stocks: string[]; crypto: string[] }) =>
  fetchAndParse("/api/config/symbols", SymbolsConfigSchema, {
    method: "PUT",
    body: JSON.stringify(symbols),
  });

// ---------------------------------------------------------------------------
// Market
// ---------------------------------------------------------------------------
export const getOHLC = (symbol: string, interval = "1h", limit = 500) =>
  fetchAndParse(
    `/api/market/ohlc/${encodeURIComponent(symbol)}?interval=${interval}&limit=${limit}`,
    z.array(OHLCBarSchema),
  );
export const getMarketPrices = () => fetchAndParse("/api/market/prices", MarketPricesSchema);
export const getSparklines = () => fetchAndParse("/api/market/sparklines", SparklineMapSchema);

// ---------------------------------------------------------------------------
// System
// ---------------------------------------------------------------------------
export const getHealth = () => fetchAndParse("/api/health", HealthStatusSchema);
export const getSystemStatus = () => fetchAndParse("/api/system/status", SystemStatusSchema);
export const killSwitch = () =>
  fetchAndParse("/api/kill", StatusResponseSchema, { method: "POST" });
export const pauseTrading = () =>
  fetchAndParse("/api/pause", StatusResponseSchema, { method: "POST" });
export const resumeTrading = () =>
  fetchAndParse("/api/resume", StatusResponseSchema, { method: "POST" });

// ---------------------------------------------------------------------------
// Simulation
// ---------------------------------------------------------------------------
export const runSimulation = (config: {
  stocks: string[];
  initial_balance: number;
  train_days: number;
  test_days: number;
  risk_levels: string[];
  mc_simulations: number;
  mc_seed?: number | null;
  max_position_pct?: number | null;
  portfolio_mode?: boolean;
  allocation_mode?: string;
  custom_weights?: Record<string, number>;
  rebalance_frequency?: string;
  rebalance_threshold_pct?: number;
}) =>
  fetchAndParse("/api/simulation/run", SimulationRunSchema, {
    method: "POST",
    body: JSON.stringify(config),
  });
export const getSimulationRuns = () =>
  fetchAndParse("/api/simulation/runs", z.array(SimulationRunSchema));
export const getSimulationRun = (id: string) =>
  fetchAndParse(`/api/simulation/runs/${id}`, SimulationRunSchema);
