import { z } from "zod";

export const PlaceOrderInputSchema = z.object({
  symbol: z.string(),
  side: z.string(),
  order_type: z.string(),
  quantity: z.number(),
  limit_price: z.number().optional(),
});

export type PlaceOrderInput = z.infer<typeof PlaceOrderInputSchema>;

export const UpdateRiskSettingsSchema = z
  .object({
    max_position_pct: z.number().optional(),
    max_sector_exposure_pct: z.number().optional(),
    daily_loss_limit_pct: z.number().optional(),
    weekly_drawdown_limit_pct: z.number().optional(),
    max_open_positions: z.number().optional(),
    stop_loss_pct: z.number().optional(),
    trailing_stop_enabled: z.boolean().optional(),
    trailing_stop_pct: z.number().optional(),
    max_correlation: z.number().optional(),
  })
  .passthrough();

export type UpdateRiskSettings = z.infer<typeof UpdateRiskSettingsSchema>;

export const ApplyPresetSchema = z.object({
  level: z.string(),
});

export type ApplyPreset = z.infer<typeof ApplyPresetSchema>;

export const UpdateSymbolsSchema = z.object({
  stocks: z.array(z.string()),
  crypto: z.array(z.string()),
});

export type UpdateSymbols = z.infer<typeof UpdateSymbolsSchema>;
