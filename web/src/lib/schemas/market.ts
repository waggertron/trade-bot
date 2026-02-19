import { z } from "zod";

export const MarketPricesSchema = z.record(z.string(), z.string());

export type MarketPrices = z.infer<typeof MarketPricesSchema>;

export const OHLCBarSchema = z
  .object({
    timestamp: z.number(),
    open: z.string(),
    high: z.string(),
    low: z.string(),
    close: z.string(),
    volume: z.string(),
  })
  .passthrough();

export type OHLCBar = z.infer<typeof OHLCBarSchema>;

export const SparklineDataSchema = z
  .object({
    prices: z.array(z.number()),
    current: z.number(),
    change_pct: z.number(),
  })
  .passthrough();

export type SparklineData = z.infer<typeof SparklineDataSchema>;

export const SparklineMapSchema = z.record(z.string(), SparklineDataSchema);

export type SparklineMap = z.infer<typeof SparklineMapSchema>;
