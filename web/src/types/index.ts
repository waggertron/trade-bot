// Re-export types from Zod schemas (single source of truth)

export type { Attribution, Correlation, DrawdownSeries, MonteCarlo } from "@/lib/schemas/analytics";
export type { BacktestResult, BacktestRun } from "@/lib/schemas/backtest";
export type {
  Config,
  HealthStatus,
  SymbolsConfig,
  SystemStatus,
  TradeMode,
} from "@/lib/schemas/config";
export type {
  ApplyPreset,
  PlaceOrderInput,
  UpdateRiskSettings,
  UpdateSymbols,
} from "@/lib/schemas/inputs";
export type { MarketPrices, OHLCBar, SparklineData, SparklineMap } from "@/lib/schemas/market";
export type {
  FeatureCatalog,
  FeatureImportance,
  FeatureStatus,
  MLModel,
  Predictions,
} from "@/lib/schemas/ml";
export type {
  NewsArticle,
  NewsStatus,
  SentimentAggregate,
  SentimentScore,
  SentimentTrend,
} from "@/lib/schemas/news";
export type {
  Allocation,
  EquityCurve,
  PnLSummary,
  Portfolio,
  Position,
} from "@/lib/schemas/portfolio";
export type {
  CircuitBreaker,
  DrawdownStatus,
  RiskDecision,
  RiskPresets,
  RiskSettings,
  RiskStatus,
} from "@/lib/schemas/risk";
export type { Recommendation, SimulationConfig, SimulationRun } from "@/lib/schemas/simulation";
export type {
  ConsensusVotes,
  StrategyInfo,
  StrategyStats,
  StrategyStatus,
} from "@/lib/schemas/strategies";
export type { Signal, Trade } from "@/lib/schemas/trades";
export type {
  CancelAllResult,
  CancelResult,
  Order,
  OrderFill,
  PlaceOrderResponse,
  TradingPrices,
} from "@/lib/schemas/trading";

// Legacy type aliases for backward compatibility
export type AssetType = "stock" | "crypto";
export type SignalDirection = "buy" | "sell" | "hold";
export type OrderSide = "buy" | "sell";
export type OrderType = "market" | "limit";
export type RiskAction = "approve" | "veto" | "resize";
export type RiskLevel = "conservative" | "moderate" | "aggressive" | "very_aggressive";
export type VolatilityRegime = "low" | "medium" | "high";

// Legacy interface aliases
export type { Position as PortfolioSnapshot } from "@/lib/schemas/portfolio";
export type { Order as OrderResponse, OrderFill as FillResponse } from "@/lib/schemas/trading";

/** EquityPoint - used by page components for equity curve data */
export interface EquityPoint {
  timestamp: string;
  value: number;
}
