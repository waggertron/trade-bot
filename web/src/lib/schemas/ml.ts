import { z } from "zod";

export const FeatureCatalogSchema = z.record(z.string(), z.array(z.string()));

export type FeatureCatalog = z.infer<typeof FeatureCatalogSchema>;

export const FeatureStatusSchema = z
  .object({
    status: z.string(),
    last_computed: z.string(),
    features_computed: z.number(),
    symbols_covered: z.number(),
    next_update_in: z.number(),
  })
  .passthrough();

export type FeatureStatus = z.infer<typeof FeatureStatusSchema>;

export const MLModelSchema = z
  .object({
    name: z.string(),
    type: z.string(),
    accuracy: z.string(),
    last_trained: z.string(),
    features_used: z.number(),
    auc: z.number(),
  })
  .passthrough();

export type MLModel = z.infer<typeof MLModelSchema>;

export const FeatureImportanceItemSchema = z
  .object({
    name: z.string(),
    importance: z.number(),
  })
  .passthrough();

export const FeatureImportanceSchema = z
  .object({
    model: z.string(),
    features: z.array(FeatureImportanceItemSchema),
  })
  .passthrough();

export type FeatureImportance = z.infer<typeof FeatureImportanceSchema>;

export const PredictionSchema = z
  .object({
    direction: z.enum(["buy", "sell", "hold"]),
    confidence: z.number(),
    predicted_return: z.number(),
    horizon: z.string(),
  })
  .passthrough();

export const PredictionsSchema = z.record(z.string(), PredictionSchema);

export type Predictions = z.infer<typeof PredictionsSchema>;
