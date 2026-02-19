"use client";
import { useQuery } from "@tanstack/react-query";
import {
  getCircuitBreaker,
  getCurrentRegime,
  getDrawdownStatus,
  getRiskPresets,
  getRiskStatus,
} from "@/lib/api";

export function useRiskStatus() {
  return useQuery({ queryKey: ["risk-status"], queryFn: getRiskStatus, refetchInterval: 10000 });
}

export function useDrawdownStatus() {
  return useQuery({
    queryKey: ["drawdown-status"],
    queryFn: getDrawdownStatus,
    refetchInterval: 10000,
  });
}

export function useCircuitBreaker() {
  return useQuery({
    queryKey: ["circuit-breaker"],
    queryFn: getCircuitBreaker,
    refetchInterval: 10000,
  });
}

export function useRegime() {
  return useQuery({ queryKey: ["regime"], queryFn: getCurrentRegime, refetchInterval: 30000 });
}

export function useRiskPresets() {
  return useQuery({ queryKey: ["risk-presets"], queryFn: getRiskPresets });
}
