// TypeScript types mirroring Python models

export type AssetType = "stock" | "crypto";
export type SignalDirection = "buy" | "sell" | "hold";
export type OrderSide = "buy" | "sell";
export type OrderType = "market" | "limit";
export type RiskAction = "approve" | "veto" | "resize";
export type RiskLevel = "conservative" | "moderate" | "aggressive" | "very_aggressive";
export type VolatilityRegime = "low" | "medium" | "high";

export interface Position {
  symbol: string;
  quantity: string;
  avg_entry_price: string;
  current_price: string;
  market_value: string;
  unrealized_pnl: string;
  asset_type: AssetType;
  sector?: string;
}

export interface PortfolioSnapshot {
  cash: string;
  total_value: string;
  positions: Position[];
}

export interface Trade {
  id: string;
  symbol: string;
  side: string;
  quantity: string;
  price: string;
  commission?: string;
  strategy: string;
  paper: boolean;
  timestamp: string;
}

export interface Signal {
  id: string;
  symbol: string;
  direction: SignalDirection;
  confidence: number;
  strategy: string;
  reasoning: string;
  timestamp: string;
}

export interface EquityPoint {
  timestamp: string;
  value: number;
}

export interface OHLCBar {
  timestamp: number;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
}

export interface StrategyInfo {
  name: string;
  type: string;
  enabled: boolean;
  weight: number;
  description?: string;
  recent_signals?: Signal[];
}

export interface StrategyStats {
  name: string;
  total_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  max_consecutive_losses: number;
}

export interface AttributionReport {
  strategies: Record<string, StrategyStats>;
  total_pnl: number;
  best_strategy: string;
  worst_strategy: string;
}

export interface MonteCarloResult {
  actual_final_value: number;
  percentile: number;
  median_simulated: number;
  p5_simulated: number;
  p95_simulated: number;
  worst_drawdown_p95: number;
  n_simulations: number;
}

export interface RiskSettings {
  max_position_pct: number;
  max_sector_exposure_pct: number;
  daily_loss_limit_pct: number;
  weekly_drawdown_limit_pct: number;
  max_open_positions: number;
  stop_loss_pct: number;
  trailing_stop_enabled: boolean;
  trailing_stop_pct: number;
  max_correlation: number;
}

export interface DrawdownStatus {
  daily_pct: number;
  daily_limit: number;
  weekly_pct: number;
  weekly_limit: number;
  positions_used: number;
  positions_limit: number;
}

export interface SystemStatus {
  mode: string;
  is_paused: boolean;
  uptime_seconds: number;
  strategies_count: number;
}

export interface SparklineData {
  prices: number[];
  current: number;
  change_pct: number;
}

export interface PnLSummary {
  realized_pnl: string;
  unrealized_pnl: string;
  total_pnl: string;
  win_rate: number;
  total_trades: number;
  winning_trades: number;
}

export interface BacktestRun {
  id: string;
  status: string;
  config: {
    start_date: string;
    end_date: string;
    strategies: string[];
    symbols: string[];
    initial_capital: number;
  };
  started_at: string;
  result: Record<string, unknown> | null;
}

export interface OrderResponse {
  id: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: string;
  limit_price?: string;
  status: string;
}

export interface FillResponse {
  id: string;
  order_id: string;
  symbol: string;
  side: string;
  quantity: string;
  fill_price: string;
  timestamp: string;
}
