import { ALL_SYMBOLS, BASE_PRICES, STRATEGY_NAMES } from "./data/constants";
import { seededRandom } from "./generators";

type EventHandler = (data: Record<string, unknown>) => void;

/**
 * MockWebSocket that mimics the ReconnectingWebSocket interface.
 * Emits periodic events to simulate live data.
 */
export class MockWebSocket {
  private handlers: Map<string, Set<EventHandler>> = new Map();
  private intervals: ReturnType<typeof setInterval>[] = [];
  private rng = seededRandom(Date.now());

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  constructor(_url: string) {
    // URL is ignored in mock mode
  }

  connect() {
    // Price updates every 3s
    this.intervals.push(
      setInterval(() => {
        const symbol = ALL_SYMBOLS[Math.floor(this.rng() * ALL_SYMBOLS.length)];
        const base = BASE_PRICES[symbol];
        const change = (this.rng() - 0.5) * 0.002 * base;
        this.emit("price_update", {
          symbol,
          price: (base + change).toFixed(2),
          timestamp: new Date().toISOString(),
        });
      }, 3000),
    );

    // Trade executed every 30-60s
    this.intervals.push(
      setInterval(() => {
        if (this.rng() > 0.5) return; // 50% chance
        const symbol = ALL_SYMBOLS[Math.floor(this.rng() * ALL_SYMBOLS.length)];
        const side = this.rng() > 0.5 ? "buy" : "sell";
        const isCrypto = symbol.includes("/");
        const quantity = isCrypto
          ? (this.rng() * 2 + 0.1).toFixed(4)
          : String(Math.floor(this.rng() * 50 + 10));
        this.emit("trade_executed", {
          symbol,
          side,
          quantity,
          price: BASE_PRICES[symbol].toFixed(2),
          strategy: STRATEGY_NAMES[Math.floor(this.rng() * STRATEGY_NAMES.length)],
          timestamp: new Date().toISOString(),
        });
      }, 30000),
    );

    // New signal every 25s
    this.intervals.push(
      setInterval(() => {
        const symbol = ALL_SYMBOLS[Math.floor(this.rng() * ALL_SYMBOLS.length)];
        const directions = ["buy", "sell", "hold"] as const;
        this.emit("signal", {
          symbol,
          direction: directions[Math.floor(this.rng() * 3)],
          confidence: Math.round(this.rng() * 60 + 30) / 100,
          strategy: STRATEGY_NAMES[Math.floor(this.rng() * STRATEGY_NAMES.length)],
          timestamp: new Date().toISOString(),
        });
      }, 25000),
    );

    // Portfolio update every 10s
    this.intervals.push(
      setInterval(() => {
        this.emit("portfolio_update", {
          total_value: (1045000 + (this.rng() - 0.5) * 5000).toFixed(2),
          timestamp: new Date().toISOString(),
        });
      }, 10000),
    );

    // Regime change every 5min (20% chance)
    this.intervals.push(
      setInterval(() => {
        if (this.rng() > 0.2) return;
        const regimes = ["low", "medium", "high"];
        this.emit("regime_change", {
          regime: regimes[Math.floor(this.rng() * 3)],
          timestamp: new Date().toISOString(),
        });
      }, 300000),
    );
  }

  subscribe(type: string, handler: EventHandler) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    this.handlers.get(type)!.add(handler);
    return () => {
      this.handlers.get(type)?.delete(handler);
    };
  }

  disconnect() {
    for (const id of this.intervals) {
      clearInterval(id);
    }
    this.intervals = [];
  }

  private emit(type: string, data: Record<string, unknown>) {
    const handlers = this.handlers.get(type);
    if (handlers) {
      handlers.forEach((h) => h(data));
    }
    const wildcardHandlers = this.handlers.get("*");
    if (wildcardHandlers) {
      wildcardHandlers.forEach((h) => h({ type, data }));
    }
  }
}
