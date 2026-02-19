import { z } from "zod";

export const TradeModeSchema = z
  .object({
    mode: z.string(),
  })
  .passthrough();

export type TradeMode = z.infer<typeof TradeModeSchema>;

export const SymbolsConfigSchema = z
  .object({
    stocks: z.array(z.string()),
    crypto: z.array(z.string()),
  })
  .passthrough();

export type SymbolsConfig = z.infer<typeof SymbolsConfigSchema>;

export const ConfigSchema = z
  .object({
    mode: z.string(),
    symbols: SymbolsConfigSchema,
    risk: z
      .object({ max_position_pct: z.number(), daily_loss_limit_pct: z.number() })
      .passthrough(),
    exchange: z.object({ name: z.string(), paper: z.boolean() }).passthrough(),
    data_providers: z.array(z.string()),
    version: z.string(),
  })
  .passthrough();

export type Config = z.infer<typeof ConfigSchema>;

export const SystemStatusSchema = z
  .object({
    mode: z.string(),
    is_paused: z.boolean(),
    uptime_seconds: z.number(),
    strategies_count: z.number(),
    active_strategies: z.number().optional(),
    positions_count: z.number().optional(),
    last_trade: z.string().optional(),
    memory_usage_mb: z.number().optional(),
    cpu_usage_pct: z.number().optional(),
  })
  .passthrough();

export type SystemStatus = z.infer<typeof SystemStatusSchema>;

export const HealthStatusSchema = z
  .object({
    status: z.string(),
  })
  .passthrough();

export type HealthStatus = z.infer<typeof HealthStatusSchema>;
