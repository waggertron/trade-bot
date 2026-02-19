"use client";
import { useQuery } from "@tanstack/react-query";
import { getMarketPrices, getOHLC, getSparklines } from "@/lib/api";

export function useMarketPrices() {
  return useQuery({
    queryKey: ["market-prices"],
    queryFn: getMarketPrices,
    refetchInterval: 10000,
  });
}

export function useSparklines() {
  return useQuery({ queryKey: ["sparklines"], queryFn: getSparklines, refetchInterval: 30000 });
}

export function useOHLC(symbol: string, interval = "1h") {
  return useQuery({
    queryKey: ["ohlc", symbol, interval],
    queryFn: () => getOHLC(symbol, interval),
    refetchInterval: 60000,
    enabled: !!symbol,
  });
}
