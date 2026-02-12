"use client";
import { useQuery } from "@tanstack/react-query";
import { getSystemStatus, getHealth } from "@/lib/api";

export function useSystemStatus() {
  return useQuery({ queryKey: ["system-status"], queryFn: getSystemStatus, refetchInterval: 10000 });
}

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 30000 });
}
