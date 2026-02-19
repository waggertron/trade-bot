import { z } from "zod";

export const NewsArticleSchema = z
  .object({
    title: z.string(),
    summary: z.string(),
    symbol: z.string(),
    source: z.string(),
    sentiment_score: z.number(),
    timestamp: z.string(),
    url: z.string(),
  })
  .passthrough();

export type NewsArticle = z.infer<typeof NewsArticleSchema>;

export const NewsProviderSchema = z
  .object({
    name: z.string(),
    healthy: z.boolean(),
    articles_today: z.number(),
  })
  .passthrough();

export const NewsStatusSchema = z
  .object({
    providers: z.array(NewsProviderSchema),
  })
  .passthrough();

export type NewsStatus = z.infer<typeof NewsStatusSchema>;

export const SentimentScoreSchema = z
  .object({
    score: z.number(),
    articles: z.number(),
  })
  .passthrough();

export type SentimentScore = z.infer<typeof SentimentScoreSchema>;

export const SentimentAggregateSchema = z.record(z.string(), SentimentScoreSchema);

export type SentimentAggregate = z.infer<typeof SentimentAggregateSchema>;

export const SentimentTrendPointSchema = z
  .object({
    date: z.string(),
    score: z.number(),
  })
  .passthrough();

export const SentimentTrendSchema = z
  .object({
    points: z.array(SentimentTrendPointSchema),
  })
  .passthrough();

export type SentimentTrend = z.infer<typeof SentimentTrendSchema>;
