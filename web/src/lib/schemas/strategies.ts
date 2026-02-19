import { z } from "zod";
import { SignalSchema } from "./trades";

export const StrategyInfoSchema = z
  .object({
    name: z.string(),
    type: z.string(),
    enabled: z.boolean(),
    weight: z.number(),
    description: z.string().optional(),
    total_trades: z.number().optional(),
    win_rate: z.number().optional(),
    recent_signals: z.array(SignalSchema).optional(),
  })
  .passthrough();

export type StrategyInfo = z.infer<typeof StrategyInfoSchema>;

export const StrategyStatusSchema = z
  .object({
    active: z.number(),
    total: z.number(),
    mode: z.string(),
  })
  .passthrough();

export type StrategyStatus = z.infer<typeof StrategyStatusSchema>;

export const StrategyStatsSchema = z
  .object({
    name: z.string(),
    total_trades: z.number(),
    win_rate: z.number(),
    total_pnl: z.number(),
    avg_win: z.number(),
    avg_loss: z.number(),
    profit_factor: z.number(),
    max_consecutive_losses: z.number(),
    sharpe_ratio: z.number().optional(),
  })
  .passthrough();

export type StrategyStats = z.infer<typeof StrategyStatsSchema>;

export const ConsensusVoteSchema = z
  .object({
    strategy: z.string(),
    symbol: z.string(),
    confidence: z.number(),
    direction: z.enum(["buy", "sell", "hold"]),
  })
  .passthrough();

export const ConsensusVotesSchema = z
  .object({
    votes: z.array(ConsensusVoteSchema),
    symbols: z.array(z.string()),
  })
  .passthrough();

export type ConsensusVotes = z.infer<typeof ConsensusVotesSchema>;
