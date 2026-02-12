/** Simulate network latency (50-200ms) */
export function mockDelay(min = 50, max = 200): Promise<void> {
  const ms = Math.floor(Math.random() * (max - min + 1)) + min;
  return new Promise((resolve) => setTimeout(resolve, ms));
}
