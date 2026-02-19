import { z } from "zod";

export const BacktestConfigSchema = z
  .object({
    start_date: z.string(),
    end_date: z.string(),
    strategies: z.array(z.string()),
    symbols: z.array(z.string()),
    initial_capital: z.number(),
  })
  .passthrough();

export const BacktestEquityPointSchema = z
  .object({
    index: z.number(),
    value: z.number(),
  })
  .passthrough();

export const BacktestResultSchema = z
  .object({
    return_pct: z.number(),
    win_rate: z.number(),
    max_drawdown: z.number(),
    sharpe_ratio: z.number(),
    total_trades: z.number(),
    equity_curve: z.array(BacktestEquityPointSchema),
  })
  .passthrough();

export type BacktestResult = z.infer<typeof BacktestResultSchema>;

export const BacktestRunSchema = z
  .object({
    id: z.string(),
    status: z.string(),
    config: BacktestConfigSchema,
    started_at: z.string(),
    result: BacktestResultSchema.nullable().optional(),
  })
  .passthrough();

export type BacktestRun = z.infer<typeof BacktestRunSchema>;
