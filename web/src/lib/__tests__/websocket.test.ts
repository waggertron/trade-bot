import { describe, it, expect, vi, beforeEach } from "vitest";
import { ReconnectingWebSocket } from "../websocket";

// Mock global WebSocket
class MockWebSocket {
  url: string;
  readyState = 1; // OPEN
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    // Auto-fire onopen on next tick
    setTimeout(() => this.onopen?.(), 0);
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).WebSocket = MockWebSocket;

describe("ReconnectingWebSocket", () => {
  let rws: ReconnectingWebSocket;

  beforeEach(() => {
    vi.useFakeTimers();
    rws = new ReconnectingWebSocket("ws://localhost:8080/ws");
  });

  it("subscribe registers handler and returns unsubscribe", () => {
    const handler = vi.fn();
    const unsub = rws.subscribe("test", handler);
    expect(typeof unsub).toBe("function");
  });

  it("unsubscribe removes handler", () => {
    const handler = vi.fn();
    const unsub = rws.subscribe("test", handler);
    unsub();
    // After unsub, handler should not be in the internal set
    // We verify by triggering a message after connect
    rws.connect();
    vi.advanceTimersByTime(10);
    // Access the internal ws to fire onmessage
    const ws = (rws as unknown as { ws: MockWebSocket }).ws;
    ws.onmessage?.({ data: JSON.stringify({ type: "test", data: {} }) });
    expect(handler).not.toHaveBeenCalled();
  });

  it("connect creates a WebSocket", () => {
    rws.connect();
    vi.advanceTimersByTime(10);
    const ws = (rws as unknown as { ws: MockWebSocket }).ws;
    expect(ws).toBeTruthy();
    expect(ws.url).toBe("ws://localhost:8080/ws");
  });

  it("dispatches messages to type-specific handler", () => {
    const handler = vi.fn();
    rws.subscribe("price_update", handler);
    rws.connect();
    vi.advanceTimersByTime(10);
    const ws = (rws as unknown as { ws: MockWebSocket }).ws;
    ws.onmessage?.({
      data: JSON.stringify({ type: "price_update", data: { symbol: "BTC" } }),
    });
    expect(handler).toHaveBeenCalledWith({ symbol: "BTC" });
  });

  it("wildcard * handler receives all messages", () => {
    const handler = vi.fn();
    rws.subscribe("*", handler);
    rws.connect();
    vi.advanceTimersByTime(10);
    const ws = (rws as unknown as { ws: MockWebSocket }).ws;
    const msg = { type: "any_event", data: { foo: "bar" } };
    ws.onmessage?.({ data: JSON.stringify(msg) });
    expect(handler).toHaveBeenCalledWith(msg);
  });

  it("disconnect closes and nullifies ws", () => {
    rws.connect();
    vi.advanceTimersByTime(10);
    rws.disconnect();
    const ws = (rws as unknown as { ws: MockWebSocket | null }).ws;
    expect(ws).toBeNull();
  });
});
