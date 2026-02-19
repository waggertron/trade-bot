/** Deterministic PRNG so charts are stable across refetches */
export function seededRandom(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

/** Simple string hash for deterministic seeds */
export function hashString(str: string): number {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 33) ^ str.charCodeAt(i);
  }
  return hash >>> 0;
}

/**
 * Generate OHLCV bars using a geometric random walk.
 * Seed = hash(symbol + interval) so same symbol always produces the same chart shape.
 */
export function generateOHLC(
  bars: number,
  startPrice: number,
  volatility: number,
  intervalMs: number,
  seed: number,
): { timestamp: number; open: string; high: string; low: string; close: string; volume: string }[] {
  const rng = seededRandom(seed);
  const result: {
    timestamp: number;
    open: string;
    high: string;
    low: string;
    close: string;
    volume: string;
  }[] = [];
  let price = startPrice;
  const now = Date.now();
  const startTime = now - bars * intervalMs;

  for (let i = 0; i < bars; i++) {
    const open = price;
    const change = (rng() - 0.48) * volatility * price; // slight upward drift
    const close = Math.max(open + change, open * 0.5);

    const wickUp = rng() * volatility * 0.5 * price;
    const wickDown = rng() * volatility * 0.5 * price;
    const high = Math.max(open, close) + wickUp;
    const low = Math.max(Math.min(open, close) - wickDown, close * 0.1);

    const baseVolume = 1000000 + rng() * 5000000;
    const volumeSpike = Math.abs(change) / (volatility * price);
    const volume = baseVolume * (1 + volumeSpike * 3);

    result.push({
      timestamp: Math.floor((startTime + i * intervalMs) / 1000),
      open: open.toFixed(2),
      high: high.toFixed(2),
      low: low.toFixed(2),
      close: close.toFixed(2),
      volume: Math.floor(volume).toString(),
    });

    price = close;
  }

  return result;
}

/** Generate an equity curve time-series with realistic growth */
export function generateEquityCurve(
  days: number,
  startValue: number,
  dailyReturn = 0.0008,
  volatility = 0.015,
  seed = 42,
): { timestamp: string; value: number }[] {
  const rng = seededRandom(seed);
  const points: { timestamp: string; value: number }[] = [];
  let value = startValue;
  const now = new Date();

  for (let i = days; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    points.push({
      timestamp: date.toISOString(),
      value: Math.round(value * 100) / 100,
    });
    const change = dailyReturn + (rng() - 0.5) * 2 * volatility;
    value *= 1 + change;
  }

  return points;
}

/** Generate a sparkline array backwards from current price */
export function generateSparkline(
  points: number,
  current: number,
  changePct: number,
  seed = 1,
): number[] {
  const rng = seededRandom(seed);
  const startPrice = current / (1 + changePct / 100);
  const prices: number[] = [];
  let price = startPrice;
  const step = (current - startPrice) / points;

  for (let i = 0; i < points; i++) {
    price += step + (rng() - 0.5) * current * 0.005;
    prices.push(Math.round(price * 100) / 100);
  }

  // Ensure last point matches current
  prices[prices.length - 1] = current;
  return prices;
}
