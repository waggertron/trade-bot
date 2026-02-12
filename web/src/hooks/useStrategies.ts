"use client";
import { useQuery } from "@tanstack/react-query";
import { getStrategies, getConsensus, getStrategyStatus } from "@/lib/api";

export function useStrategies() {
  return useQuery({ queryKey: ["strategies"], queryFn: getStrategies, refetchInterval: 15000 });
}

export function useConsensus() {
  return useQuery({ queryKey: ["consensus"], queryFn: getConsensus, refetchInterval: 10000 });
}

export function useStrategyStatus() {
  return useQuery({ queryKey: ["strategy-status"], queryFn: getStrategyStatus, refetchInterval: 15000 });
}
