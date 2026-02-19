import { MOCK_ENABLED, getMockResponse } from "./mock";

const API_BASE = "";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  if (MOCK_ENABLED) return getMockResponse<T>(path, options);
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// Portfolio
export const getPortfolio = () => fetchAPI<Record<string, unknown>>("/api/portfolio/");
export const getPositions = () => fetchAPI<Record<string, unknown>[]>("/api/portfolio/positions");
export const getPnL = (period = "30d") => fetchAPI<Record<string, unknown>>(`/api/portfolio/pnl?period=${period}`);
export const getEquityCurve = (range = "1M") => fetchAPI<{ points: { timestamp: string; value: number }[] }>(`/api/portfolio/equity-curve?range=${range}`);
export const getAllocation = () => fetchAPI<Record<string, unknown>>("/api/portfolio/allocation");

// Trading
export const placeOrder = (order: { symbol: string; side: string; order_type: string; quantity: number; limit_price?: number }) =>
  fetchAPI<{ fill: Record<string, unknown> }>("/api/trading/order", { method: "POST", body: JSON.stringify(order) });
export const getOrders = () => fetchAPI<Record<string, unknown>[]>("/api/trading/orders");
export const cancelOrder = (id: string) => fetchAPI<{ cancelled: boolean }>(`/api/trading/orders/${id}`, { method: "DELETE" });
export const cancelAllOrders = () => fetchAPI<{ cancelled_count: number }>("/api/trading/cancel-all", { method: "POST" });
export const getTradingPrices = () => fetchAPI<Record<string, string>>("/api/trading/prices");

// Trades
export const getTrades = (params?: { strategy?: string; symbol?: string; limit?: number; offset?: number }) => {
  const sp = new URLSearchParams();
  if (params?.strategy) sp.set("strategy", params.strategy);
  if (params?.symbol) sp.set("symbol", params.symbol);
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  return fetchAPI<Record<string, unknown>[]>(`/api/trades/?${sp}`);
};
export const getTrade = (id: string) => fetchAPI<Record<string, unknown>>(`/api/trades/${id}`);

// Signals
export const getSignals = (params?: { limit?: number; strategy?: string; symbol?: string }) => {
  const sp = new URLSearchParams();
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.strategy) sp.set("strategy", params.strategy);
  if (params?.symbol) sp.set("symbol", params.symbol);
  return fetchAPI<Record<string, unknown>[]>(`/api/signals/?${sp}`);
};
export const getLatestSignals = () => fetchAPI<Record<string, unknown>[]>("/api/signals/latest");

// Strategies
export const getStrategies = () => fetchAPI<Record<string, unknown>[]>("/api/strategies/");
export const getStrategyStatus = () => fetchAPI<Record<string, unknown>>("/api/strategies/status");
export const getStrategy = (name: string) => fetchAPI<Record<string, unknown>>(`/api/strategies/${name}`);
export const updateStrategyWeight = (name: string, weight: number) =>
  fetchAPI<Record<string, unknown>>(`/api/strategies/${name}/weight`, { method: "PUT", body: JSON.stringify({ weight }) });
export const updateStrategyEnabled = (name: string, enabled: boolean) =>
  fetchAPI<Record<string, unknown>>(`/api/strategies/${name}/enabled`, { method: "PUT", body: JSON.stringify({ enabled }) });
export const getConsensus = () => fetchAPI<Record<string, unknown>>("/api/strategies/consensus");
export const getStrategySignals = (name: string) => fetchAPI<Record<string, unknown>[]>(`/api/strategies/${name}/signals`);
export const getStrategyPerformance = (name: string) => fetchAPI<Record<string, unknown>>(`/api/strategies/${name}/performance`);

// Analytics
export const getAttribution = () => fetchAPI<Record<string, unknown>>("/api/analytics/attribution");
export const getMonteCarlo = () => fetchAPI<Record<string, unknown>>("/api/analytics/monte-carlo");
export const getDrawdown = () => fetchAPI<{ points: Record<string, unknown>[] }>("/api/analytics/drawdown");
export const getCorrelation = () => fetchAPI<{ symbols: string[]; matrix: number[][] }>("/api/analytics/correlation");

// Risk
export const getRiskStatus = () => fetchAPI<Record<string, unknown>>("/api/risk/status");
export const getRiskLimits = (regime?: string) => fetchAPI<Record<string, unknown>>(`/api/risk/limits?regime=${regime || "medium"}`);
export const getAllRiskLimits = () => fetchAPI<Record<string, unknown>>("/api/risk/limits/all");
export const updateRiskSettings = (settings: Record<string, unknown>) =>
  fetchAPI<Record<string, unknown>>("/api/risk/settings", { method: "PUT", body: JSON.stringify(settings) });
export const applyRiskPreset = (level: string) =>
  fetchAPI<Record<string, unknown>>("/api/risk/preset", { method: "PUT", body: JSON.stringify({ level }) });
export const getRiskPresets = () => fetchAPI<Record<string, Record<string, unknown>>>("/api/risk/presets");
export const getCurrentRegime = () => fetchAPI<{ regime: string; description: string }>("/api/risk/regime");
export const getDrawdownStatus = () => fetchAPI<Record<string, unknown>>("/api/risk/drawdown");
export const getCircuitBreaker = () => fetchAPI<Record<string, unknown>>("/api/risk/circuit-breaker");
export const resetCircuitBreaker = () => fetchAPI<{ message: string }>("/api/risk/circuit-breaker/reset", { method: "POST" });
export const getRiskDecisions = () => fetchAPI<Record<string, unknown>[]>("/api/risk/decisions");

// Backtest
export const runBacktest = (config: { start_date: string; end_date: string; strategies: string[]; symbols: string[]; initial_capital: number }) =>
  fetchAPI<Record<string, unknown>>("/api/backtest/run", { method: "POST", body: JSON.stringify(config) });
export const getBacktestRuns = () => fetchAPI<Record<string, unknown>[]>("/api/backtest/runs");
export const getBacktestRun = (id: string) => fetchAPI<Record<string, unknown>>(`/api/backtest/runs/${id}`);

// News & Sentiment
export const getNewsStatus = () => fetchAPI<Record<string, unknown>>("/api/news/status");
export const getNewsFeeds = () => fetchAPI<Record<string, unknown>>("/api/news/feeds");
export const getNewsArticles = (params?: { symbol?: string; source?: string; limit?: number }) => {
  const sp = new URLSearchParams();
  if (params?.symbol) sp.set("symbol", params.symbol);
  if (params?.source) sp.set("source", params.source);
  if (params?.limit) sp.set("limit", String(params.limit));
  return fetchAPI<Record<string, unknown>[]>(`/api/news/articles?${sp}`);
};
export const getSentimentAggregate = () => fetchAPI<Record<string, unknown>>("/api/sentiment/aggregate");
export const getSentimentTrend = (symbol: string, period = "7d") =>
  fetchAPI<Record<string, unknown>>(`/api/sentiment/trend?symbol=${symbol}&period=${period}`);

// ML & Features
export const getFeatureCatalog = () => fetchAPI<Record<string, string[]>>("/api/features/catalog");
export const getFeatureStatus = () => fetchAPI<Record<string, unknown>>("/api/features/status");
export const getMLModels = () => fetchAPI<Record<string, unknown>[]>("/api/ml/models");
export const getModelImportance = (name: string) => fetchAPI<Record<string, unknown>>(`/api/ml/models/${name}/importance`);
export const triggerTraining = () => fetchAPI<{ status: string }>("/api/ml/train", { method: "POST" });
export const getPredictions = () => fetchAPI<Record<string, unknown>>("/api/ml/predictions");

// Config
export const getConfig = () => fetchAPI<Record<string, unknown>>("/api/config/");
export const getMode = () => fetchAPI<{ mode: string }>("/api/config/mode");
export const setMode = (mode: string) =>
  fetchAPI<{ mode: string }>("/api/config/mode", { method: "PUT", body: JSON.stringify({ mode }) });
export const getSymbols = () => fetchAPI<{ stocks: string[]; crypto: string[] }>("/api/config/symbols");
export const updateSymbols = (symbols: { stocks: string[]; crypto: string[] }) =>
  fetchAPI<Record<string, unknown>>("/api/config/symbols", { method: "PUT", body: JSON.stringify(symbols) });

// Market
export const getOHLC = (symbol: string, interval = "1h", limit = 500) =>
  fetchAPI<Record<string, unknown>[]>(`/api/market/ohlc/${encodeURIComponent(symbol)}?interval=${interval}&limit=${limit}`);
export const getMarketPrices = () => fetchAPI<Record<string, string>>("/api/market/prices");
export const getSparklines = () => fetchAPI<Record<string, { prices: number[]; current: number; change_pct: number }>>("/api/market/sparklines");

// System
export const getHealth = () => fetchAPI<{ status: string }>("/api/health");
export const getSystemStatus = () => fetchAPI<Record<string, unknown>>("/api/system/status");
export const killSwitch = () => fetchAPI<Record<string, unknown>>("/api/kill", { method: "POST" });
export const pauseTrading = () => fetchAPI<{ status: string }>("/api/pause", { method: "POST" });
export const resumeTrading = () => fetchAPI<{ status: string }>("/api/resume", { method: "POST" });

// Simulation
export const runSimulation = (config: {
  stocks: string[];
  initial_balance: number;
  train_days: number;
  test_days: number;
  risk_levels: string[];
  mc_simulations: number;
}) =>
  fetchAPI<Record<string, unknown>>("/api/simulation/run", {
    method: "POST",
    body: JSON.stringify(config),
  });
export const getSimulationRuns = () =>
  fetchAPI<Record<string, unknown>[]>("/api/simulation/runs");
export const getSimulationRun = (id: string) =>
  fetchAPI<Record<string, unknown>>(`/api/simulation/runs/${id}`);
