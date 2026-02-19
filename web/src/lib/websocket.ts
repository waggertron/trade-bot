type EventHandler = (data: Record<string, unknown>) => void;

export class ReconnectingWebSocket {
  private ws: WebSocket | null = null;
  private url: string;
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private reconnectDelay = 1000;
  private maxDelay = 30000;
  private pingInterval: ReturnType<typeof setInterval> | null = null;

  constructor(url: string) {
    this.url = url;
  }

  connect() {
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectDelay = 1000;
        this.startPing();
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const type = msg.type as string;
          const handlers = this.handlers.get(type);
          if (handlers) {
            handlers.forEach((h) => {
              h(msg.data);
            });
          }
          // Also fire wildcard handlers
          const wildcardHandlers = this.handlers.get("*");
          if (wildcardHandlers) {
            wildcardHandlers.forEach((h) => {
              h(msg);
            });
          }
        } catch {
          // ignore parse errors
        }
      };

      this.ws.onclose = () => {
        this.stopPing();
        setTimeout(() => this.connect(), this.reconnectDelay);
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay);
      };

      this.ws.onerror = () => {
        this.ws?.close();
      };
    } catch {
      setTimeout(() => this.connect(), this.reconnectDelay);
    }
  }

  subscribe(type: string, handler: EventHandler) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)?.add(handler);
    return () => {
      this.handlers.get(type)?.delete(handler);
    };
  }

  disconnect() {
    this.stopPing();
    this.ws?.close();
    this.ws = null;
  }

  private startPing() {
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);
  }

  private stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
}
