import { z } from "zod";

export const PositionSchema = z
  .object({
    symbol: z.string(),
    quantity: z.string(),
    avg_entry_price: z.string(),
    current_price: z.string(),
    market_value: z.string(),
    unrealized_pnl: z.string(),
    asset_type: z.enum(["stock", "crypto"]),
    sector: z.string().optional(),
  })
  .passthrough();

export type Position = z.infer<typeof PositionSchema>;

export const PortfolioSchema = z
  .object({
    cash: z.string(),
    total_value: z.string(),
    positions: z.array(PositionSchema),
  })
  .passthrough();

export type Portfolio = z.infer<typeof PortfolioSchema>;

export const PnLSummarySchema = z
  .object({
    realized_pnl: z.string(),
    unrealized_pnl: z.string(),
    total_pnl: z.string(),
    win_rate: z.number(),
    total_trades: z.number(),
    winning_trades: z.number(),
  })
  .passthrough();

export type PnLSummary = z.infer<typeof PnLSummarySchema>;

export const EquityPointSchema = z
  .object({
    timestamp: z.string(),
    value: z.number(),
  })
  .passthrough();

export const EquityCurveSchema = z
  .object({
    points: z.array(EquityPointSchema),
  })
  .passthrough();

export type EquityCurve = z.infer<typeof EquityCurveSchema>;

export const AllocationSchema = z
  .object({
    by_type: z.object({ stock: z.number(), crypto: z.number() }).passthrough(),
    by_sector: z.record(z.string(), z.number()),
    cash_pct: z.number(),
  })
  .passthrough();

export type Allocation = z.infer<typeof AllocationSchema>;
