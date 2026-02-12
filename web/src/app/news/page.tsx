"use client";

import { useQuery } from "@tanstack/react-query";
import { getNewsArticles, getNewsStatus, getSentimentAggregate, getSentimentTrend } from "@/lib/api";
import ChartContainer from "@/components/shared/ChartContainer";
import { ChartSkeleton } from "@/components/shared/LoadingSkeleton";
import { Newspaper, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn, formatTimeAgo } from "@/lib/formatters";

function SentimentBadge({ score }: { score: number }) {
  if (score > 0.2) return <span className="rounded-full bg-profit/20 px-2 py-0.5 text-xs text-profit">Bullish</span>;
  if (score < -0.2) return <span className="rounded-full bg-loss/20 px-2 py-0.5 text-xs text-loss">Bearish</span>;
  return <span className="rounded-full bg-muted/20 px-2 py-0.5 text-xs text-muted">Neutral</span>;
}

export default function NewsPage() {
  const { data: articles, isLoading } = useQuery({
    queryKey: ["news-articles"], queryFn: () => getNewsArticles({ limit: 50 }), refetchInterval: 60000,
  });
  const { data: newsStatus } = useQuery({
    queryKey: ["news-status"], queryFn: getNewsStatus,
  });
  const { data: sentiment } = useQuery({
    queryKey: ["sentiment-aggregate"], queryFn: getSentimentAggregate,
  });

  const articleList = (articles || []) as Record<string, unknown>[];
  const sentimentData = (sentiment || {}) as Record<string, unknown>;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">News & Sentiment</h1>

      <div className="grid grid-cols-5 gap-6">
        {/* News feed */}
        <div className="col-span-3 space-y-3">
          <ChartContainer title="News Feed" subtitle={`${articleList.length} articles`}>
            {isLoading ? (
              <ChartSkeleton height="h-96" />
            ) : articleList.length === 0 ? (
              <div className="py-16 text-center text-muted">
                <Newspaper size={32} className="mx-auto mb-3" />
                <p className="text-sm">No news articles available</p>
                <p className="mt-1 text-xs">News providers will populate articles when configured</p>
              </div>
            ) : (
              <div className="max-h-[600px] space-y-2 overflow-y-auto">
                {articleList.map((article, i) => (
                  <div key={i} className="rounded-lg border border-border/50 p-3 hover:bg-card-hover/50">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1">
                        <p className="text-sm font-medium text-foreground">{article.title as string || "Untitled"}</p>
                        <p className="mt-1 text-xs text-muted line-clamp-2">{article.summary as string || ""}</p>
                        <div className="mt-2 flex items-center gap-2">
                          {typeof article.symbol === "string" && (
                            <span className="rounded bg-accent/10 px-1.5 py-0.5 text-xs text-accent">{article.symbol}</span>
                          )}
                          {typeof article.source === "string" && (
                            <span className="text-xs text-muted">{article.source}</span>
                          )}
                          {typeof article.timestamp === "string" && (
                            <span className="text-xs text-muted">{formatTimeAgo(article.timestamp)}</span>
                          )}
                        </div>
                      </div>
                      {article.sentiment_score !== undefined && (
                        <SentimentBadge score={article.sentiment_score as number} />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ChartContainer>
        </div>

        {/* Sentiment dashboard */}
        <div className="col-span-2 space-y-4">
          <ChartContainer title="Sentiment Overview" subtitle="Aggregate by symbol">
            {Object.keys(sentimentData).length === 0 ? (
              <div className="py-12 text-center text-muted">
                <TrendingUp size={24} className="mx-auto mb-2" />
                <p className="text-xs">Sentiment data will appear when providers are active</p>
              </div>
            ) : (
              <div className="space-y-3">
                {Object.entries(sentimentData).map(([symbol, data]) => {
                  const score = (data as Record<string, unknown>)?.score as number || 0;
                  return (
                    <div key={symbol} className="flex items-center justify-between rounded-lg bg-background p-3">
                      <span className="text-sm font-medium">{symbol}</span>
                      <div className="flex items-center gap-2">
                        {score > 0 ? <TrendingUp size={14} className="text-profit" /> :
                         score < 0 ? <TrendingDown size={14} className="text-loss" /> :
                         <Minus size={14} className="text-muted" />}
                        <span className={cn("text-sm font-medium",
                          score > 0 ? "text-profit" : score < 0 ? "text-loss" : "text-muted"
                        )}>
                          {score.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </ChartContainer>

          <ChartContainer title="Provider Status">
            <div className="space-y-2">
              {(newsStatus as Record<string, unknown>)?.providers ? (
                ((newsStatus as Record<string, unknown>).providers as Record<string, unknown>[]).map((p, i) => (
                  <div key={i} className="flex items-center justify-between rounded-lg bg-background p-3">
                    <span className="text-sm">{p.name as string}</span>
                    <span className={cn("rounded-full px-2 py-0.5 text-xs",
                      p.healthy ? "bg-profit/20 text-profit" : "bg-loss/20 text-loss"
                    )}>
                      {p.healthy ? "Healthy" : "Down"}
                    </span>
                  </div>
                ))
              ) : (
                <p className="py-4 text-center text-xs text-muted">No providers configured</p>
              )}
            </div>
          </ChartContainer>
        </div>
      </div>
    </div>
  );
}
