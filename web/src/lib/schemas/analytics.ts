import { z } from "zod";
import { StrategyStatsSchema } from "./strategies";

export const AttributionSchema = z
  .object({
    strategies: z.record(z.string(), StrategyStatsSchema),
    total_pnl: z.number(),
    best_strategy: z.string(),
    worst_strategy: z.string(),
  })
  .passthrough();

export type Attribution = z.infer<typeof AttributionSchema>;

export const MonteCarloSchema = z
  .object({
    actual_final_value: z.number(),
    percentile: z.number(),
    median_simulated: z.number(),
    p5_simulated: z.number(),
    p95_simulated: z.number(),
    worst_drawdown_p95: z.number(),
    n_simulations: z.number(),
  })
  .passthrough();

export type MonteCarlo = z.infer<typeof MonteCarloSchema>;

export const DrawdownPointSchema = z
  .object({
    index: z.number(),
    drawdown_pct: z.number(),
    value: z.number(),
  })
  .passthrough();

export const DrawdownSeriesSchema = z
  .object({
    points: z.array(DrawdownPointSchema),
  })
  .passthrough();

export type DrawdownSeries = z.infer<typeof DrawdownSeriesSchema>;

export const CorrelationSchema = z
  .object({
    symbols: z.array(z.string()),
    matrix: z.array(z.array(z.number())),
  })
  .passthrough();

export type Correlation = z.infer<typeof CorrelationSchema>;
