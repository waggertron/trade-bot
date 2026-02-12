"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ReconnectingWebSocket } from "@/lib/websocket";
import { useNotificationStore } from "@/stores/notificationStore";

/**
 * Establishes a WebSocket connection to the backend and routes
 * incoming events to React Query cache invalidation and toast
 * notifications. Should be mounted once in the root layout.
 */
export function useWebSocket() {
  const queryClient = useQueryClient();
  const addNotification = useNotificationStore((s) => s.add);
  const wsRef = useRef<ReconnectingWebSocket | null>(null);

  useEffect(() => {
    const wsUrl =
      typeof window !== "undefined"
        ? `ws://${window.location.hostname}:8080/api/ws`
        : "ws://localhost:8080/api/ws";

    const ws = new ReconnectingWebSocket(wsUrl);
    wsRef.current = ws;

    // Price updates → invalidate market queries
    ws.subscribe("price_update", () => {
      queryClient.invalidateQueries({ queryKey: ["market-prices"] });
      queryClient.invalidateQueries({ queryKey: ["sparklines"] });
    });

    // Trade executed → invalidate portfolio + trades + orders
    ws.subscribe("trade_executed", (data) => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["trades"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["pnl"] });
      queryClient.invalidateQueries({ queryKey: ["equity-curve"] });

      addNotification({
        type: "success",
        title: "Trade Executed",
        message: `${(data.side as string)?.toUpperCase() ?? ""} ${data.quantity ?? ""} ${data.symbol ?? ""}`,
      });
    });

    // New signal → invalidate signals
    ws.subscribe("signal", () => {
      queryClient.invalidateQueries({ queryKey: ["signals"] });
      queryClient.invalidateQueries({ queryKey: ["latest-signals"] });
      queryClient.invalidateQueries({ queryKey: ["consensus"] });
    });

    // Portfolio update → invalidate portfolio queries
    ws.subscribe("portfolio_update", () => {
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["allocation"] });
      queryClient.invalidateQueries({ queryKey: ["equity-curve"] });
    });

    // Risk alert → show warning notification
    ws.subscribe("risk_alert", (data) => {
      addNotification({
        type: "warning",
        title: "Risk Alert",
        message: (data.message as string) ?? "Risk threshold approaching",
      });
      queryClient.invalidateQueries({ queryKey: ["risk-status"] });
      queryClient.invalidateQueries({ queryKey: ["drawdown"] });
    });

    // Circuit breaker → show error notification
    ws.subscribe("circuit_breaker", (data) => {
      const tripped = data.tripped as boolean;
      addNotification({
        type: tripped ? "error" : "info",
        title: tripped ? "Circuit Breaker Tripped" : "Circuit Breaker Reset",
        message: tripped
          ? "Trading halted — drawdown exceeded threshold"
          : "Trading resumed",
      });
      queryClient.invalidateQueries({ queryKey: ["circuit-breaker"] });
      queryClient.invalidateQueries({ queryKey: ["risk-status"] });
    });

    // Regime change → invalidate regime queries
    ws.subscribe("regime_change", (data) => {
      addNotification({
        type: "info",
        title: "Regime Change",
        message: `Volatility regime: ${(data.regime as string) ?? "unknown"}`,
      });
      queryClient.invalidateQueries({ queryKey: ["regime"] });
      queryClient.invalidateQueries({ queryKey: ["risk-status"] });
    });

    ws.connect();

    return () => {
      ws.disconnect();
      wsRef.current = null;
    };
  }, [queryClient, addNotification]);
}
