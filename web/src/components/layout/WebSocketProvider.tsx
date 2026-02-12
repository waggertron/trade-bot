"use client";

import { useWebSocket } from "@/hooks/useWebSocket";

/** Establishes the WebSocket connection once at the root layout level. */
export default function WebSocketProvider() {
  useWebSocket();
  return null;
}
