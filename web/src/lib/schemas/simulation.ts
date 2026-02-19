import { z } from "zod";

export const SimulationConfigSchema = z
  .object({
    stocks: z.array(z.string()),
    initial_balance: z.number(),
    train_days: z.number(),
    test_days: z.number(),
    risk_levels: z.array(z.string()),
    mc_simulations: z.number(),
  })
  .passthrough();

export type SimulationConfig = z.infer<typeof SimulationConfigSchema>;

export const StockResultSchema = z
  .object({
    symbol: z.string(),
    return_pct: z.number(),
    sharpe_ratio: z.number(),
    max_drawdown: z.number(),
    win_rate: z.number(),
    total_trades: z.number(),
    initial_balance: z.number(),
    final_value: z.number(),
    total_pnl: z.number(),
    winning_trades: z.number(),
    losing_trades: z.number(),
    equity_curve: z.array(z.unknown()),
  })
  .passthrough();

export const MonteCarloProjectionSchema = z
  .object({
    symbol: z.string(),
    median_final: z.number(),
    p5_final: z.number(),
    p95_final: z.number(),
    median_return_pct: z.number(),
    p5_return_pct: z.number(),
    p95_return_pct: z.number(),
    worst_drawdown_p95: z.number(),
    n_paths: z.number(),
  })
  .passthrough();

export const RiskLevelResultSchema = z
  .object({
    risk_level: z.string(),
    total_return_pct: z.number(),
    avg_sharpe: z.number(),
    avg_max_drawdown: z.number(),
    total_trades: z.number(),
    stock_results: z.array(StockResultSchema),
    monte_carlo_projections: z.array(MonteCarloProjectionSchema),
    strategy_assessments: z.array(z.unknown()),
  })
  .passthrough();

export const RecommendationSchema = z
  .object({
    optimal_risk_level: z.string(),
    reasoning: z.string(),
    suggested_weights: z.record(z.string(), z.number()),
    confidence: z.number(),
  })
  .passthrough();

export type Recommendation = z.infer<typeof RecommendationSchema>;

export const SimulationRunSchema = z
  .object({
    id: z.string(),
    status: z.string(),
    config: SimulationConfigSchema,
    risk_level_results: z.record(z.string(), RiskLevelResultSchema),
    recommendation: RecommendationSchema,
    started_at: z.string(),
    completed_at: z.string().optional(),
    error: z.string().nullable().optional(),
  })
  .passthrough();

export type SimulationRun = z.infer<typeof SimulationRunSchema>;
