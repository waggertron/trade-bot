export const STOCK_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"];
export const CRYPTO_SYMBOLS = ["BTC/USD", "ETH/USD", "SOL/USD"];
export const ALL_SYMBOLS = [...STOCK_SYMBOLS, ...CRYPTO_SYMBOLS];

export const STRATEGY_NAMES = [
  "momentum_breakout",
  "mean_reversion",
  "sentiment_alpha",
  "ml_ensemble",
  "pairs_trading",
  "trend_following",
] as const;

export const STRATEGY_TYPES: Record<string, string> = {
  momentum_breakout: "momentum",
  mean_reversion: "mean_reversion",
  sentiment_alpha: "sentiment",
  ml_ensemble: "ml",
  pairs_trading: "statistical_arb",
  trend_following: "trend",
};

export const STRATEGY_DESCRIPTIONS: Record<string, string> = {
  momentum_breakout: "Detects breakout patterns in price momentum using RSI and MACD",
  mean_reversion: "Identifies overbought/oversold conditions for mean reversion trades",
  sentiment_alpha: "Analyzes news and social media sentiment to generate alpha signals",
  ml_ensemble: "Ensemble of gradient boosting and neural network models",
  pairs_trading: "Statistical arbitrage between correlated asset pairs",
  trend_following: "Multi-timeframe trend following using moving average crossovers",
};

export const SECTORS: Record<string, string> = {
  AAPL: "Technology",
  MSFT: "Technology",
  GOOGL: "Technology",
  AMZN: "Consumer Discretionary",
  TSLA: "Consumer Discretionary",
  NVDA: "Technology",
  META: "Technology",
  "BTC/USD": "Crypto",
  "ETH/USD": "Crypto",
  "SOL/USD": "Crypto",
};

export const BASE_PRICES: Record<string, number> = {
  AAPL: 198.50,
  MSFT: 420.75,
  GOOGL: 175.30,
  AMZN: 195.60,
  TSLA: 248.90,
  NVDA: 875.40,
  META: 525.10,
  "BTC/USD": 97450.00,
  "ETH/USD": 3285.00,
  "SOL/USD": 192.50,
};

/** Interval string to milliseconds */
export const INTERVAL_MS: Record<string, number> = {
  "1m": 60_000,
  "5m": 300_000,
  "15m": 900_000,
  "1h": 3_600_000,
  "4h": 14_400_000,
  "1d": 86_400_000,
};

export const NEWS_SOURCES = ["Bloomberg", "Reuters", "CNBC", "CoinDesk", "MarketWatch", "WSJ"];
