"use client";
import { useQuery } from "@tanstack/react-query";
import { getPortfolio, getPositions, getPnL, getEquityCurve, getAllocation } from "@/lib/api";

export function usePortfolio() {
  return useQuery({ queryKey: ["portfolio"], queryFn: getPortfolio, refetchInterval: 10000 });
}

export function usePositions() {
  return useQuery({ queryKey: ["positions"], queryFn: getPositions, refetchInterval: 10000 });
}

export function usePnL(period = "30d") {
  return useQuery({ queryKey: ["pnl", period], queryFn: () => getPnL(period), refetchInterval: 15000 });
}

export function useEquityCurve(range = "1M") {
  return useQuery({ queryKey: ["equity-curve", range], queryFn: () => getEquityCurve(range), refetchInterval: 30000 });
}

export function useAllocation() {
  return useQuery({ queryKey: ["allocation"], queryFn: getAllocation, refetchInterval: 30000 });
}
