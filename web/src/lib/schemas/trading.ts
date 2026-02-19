import { z } from "zod";

export const OrderSchema = z
  .object({
    id: z.string(),
    symbol: z.string(),
    side: z.string(),
    order_type: z.string(),
    quantity: z.string(),
    limit_price: z.string().optional(),
    status: z.string(),
    created_at: z.string(),
  })
  .passthrough();

export type Order = z.infer<typeof OrderSchema>;

export const OrderFillSchema = z
  .object({
    id: z.string(),
    symbol: z.string(),
    side: z.string(),
    quantity: z.string(),
    fill_price: z.string(),
    timestamp: z.string(),
  })
  .passthrough();

export type OrderFill = z.infer<typeof OrderFillSchema>;

export const PlaceOrderResponseSchema = z
  .object({
    fill: OrderFillSchema,
  })
  .passthrough();

export type PlaceOrderResponse = z.infer<typeof PlaceOrderResponseSchema>;

export const TradingPricesSchema = z.record(z.string(), z.string());

export type TradingPrices = z.infer<typeof TradingPricesSchema>;

export const CancelResultSchema = z
  .object({
    cancelled: z.boolean(),
  })
  .passthrough();

export type CancelResult = z.infer<typeof CancelResultSchema>;

export const CancelAllResultSchema = z
  .object({
    cancelled_count: z.number(),
  })
  .passthrough();

export type CancelAllResult = z.infer<typeof CancelAllResultSchema>;
