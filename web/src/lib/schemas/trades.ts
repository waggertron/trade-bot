import { z } from "zod";

export const TradeSchema = z
  .object({
    id: z.string(),
    symbol: z.string(),
    side: z.string(),
    quantity: z.string(),
    price: z.string(),
    commission: z.string().optional(),
    strategy: z.string(),
    paper: z.boolean(),
    timestamp: z.string(),
  })
  .passthrough();

export type Trade = z.infer<typeof TradeSchema>;

export const SignalSchema = z
  .object({
    id: z.string(),
    symbol: z.string(),
    direction: z.enum(["buy", "sell", "hold"]),
    confidence: z.number(),
    strategy: z.string(),
    reasoning: z.string(),
    timestamp: z.string(),
  })
  .passthrough();

export type Signal = z.infer<typeof SignalSchema>;
