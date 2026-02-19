import { z } from "zod";

export const RiskSettingsSchema = z
  .object({
    max_position_pct: z.number(),
    max_sector_exposure_pct: z.number(),
    daily_loss_limit_pct: z.number(),
    weekly_drawdown_limit_pct: z.number(),
    max_open_positions: z.number(),
    stop_loss_pct: z.number(),
    trailing_stop_enabled: z.boolean().optional(),
    trailing_stop_pct: z.number(),
    max_correlation: z.number(),
  })
  .passthrough();

export type RiskSettings = z.infer<typeof RiskSettingsSchema>;

export const RiskStatusSchema = z
  .object({
    max_position_pct: z.number(),
    max_sector_exposure_pct: z.number(),
    daily_loss_limit_pct: z.number(),
    weekly_drawdown_limit_pct: z.number(),
    max_open_positions: z.number(),
    stop_loss_pct: z.number(),
    trailing_stop_enabled: z.boolean(),
    trailing_stop_pct: z.number(),
    max_correlation: z.number(),
    status: z.string(),
    regime: z.string(),
  })
  .passthrough();

export type RiskStatus = z.infer<typeof RiskStatusSchema>;

export const DrawdownStatusSchema = z
  .object({
    daily_pct: z.number(),
    daily_limit: z.number(),
    weekly_pct: z.number(),
    weekly_limit: z.number(),
    positions_used: z.number(),
    positions_limit: z.number(),
  })
  .passthrough();

export type DrawdownStatus = z.infer<typeof DrawdownStatusSchema>;

export const CircuitBreakerSchema = z
  .object({
    tripped: z.boolean(),
    tripped_at: z.string().nullable(),
    reason: z.string().nullable(),
    daily_loss_pct: z.number(),
    threshold_pct: z.number(),
  })
  .passthrough();

export type CircuitBreaker = z.infer<typeof CircuitBreakerSchema>;

export const RiskDecisionSchema = z
  .object({
    id: z.string(),
    action: z.enum(["approve", "veto", "resize"]),
    symbol: z.string(),
    reason: z.string(),
    timestamp: z.string(),
  })
  .passthrough();

export type RiskDecision = z.infer<typeof RiskDecisionSchema>;

export const RiskPresetsSchema = z.record(z.string(), RiskSettingsSchema.partial());

export type RiskPresets = z.infer<typeof RiskPresetsSchema>;
