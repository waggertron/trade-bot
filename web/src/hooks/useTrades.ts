"use client";
import { useQuery } from "@tanstack/react-query";
import { getLatestSignals, getSignals, getTrades } from "@/lib/api";

export function useTrades(params?: { strategy?: string; symbol?: string; limit?: number }) {
  return useQuery({
    queryKey: ["trades", params],
    queryFn: () => getTrades(params),
    refetchInterval: 15000,
  });
}

export function useSignals(params?: { limit?: number; strategy?: string; symbol?: string }) {
  return useQuery({
    queryKey: ["signals", params],
    queryFn: () => getSignals(params),
    refetchInterval: 10000,
  });
}

export function useLatestSignals() {
  return useQuery({
    queryKey: ["signals", "latest"],
    queryFn: getLatestSignals,
    refetchInterval: 10000,
  });
}
