import { registerRoute } from "../router";
import { ALL_SYMBOLS } from "./constants";

// ---------------------------------------------------------------------------
// GET /api/features/catalog
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/features\/catalog$/, () => {
  return {
    technical: [
      "rsi_14",
      "rsi_28",
      "macd_signal",
      "macd_histogram",
      "bollinger_upper",
      "bollinger_lower",
      "sma_20",
      "sma_50",
      "sma_200",
      "ema_12",
      "ema_26",
      "atr_14",
      "obv",
      "vwap",
      "stochastic_k",
      "stochastic_d",
    ],
    momentum: [
      "price_momentum_5d",
      "price_momentum_10d",
      "price_momentum_20d",
      "volume_momentum_5d",
      "rate_of_change_14",
      "williams_r",
    ],
    sentiment: [
      "news_sentiment_24h",
      "news_sentiment_7d",
      "social_mention_volume",
      "fear_greed_index",
      "put_call_ratio",
      "short_interest_ratio",
    ],
    fundamental: [
      "pe_ratio",
      "pb_ratio",
      "dividend_yield",
      "market_cap_rank",
      "earnings_surprise",
      "revenue_growth_yoy",
    ],
    market_structure: [
      "bid_ask_spread",
      "order_book_imbalance",
      "trade_flow_toxicity",
      "realized_volatility_20d",
      "implied_volatility",
      "correlation_spy",
    ],
  };
});

// ---------------------------------------------------------------------------
// GET /api/features/status
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/features\/status$/, () => {
  return {
    status: "running",
    last_computed: new Date(Date.now() - 300000).toISOString(),
    features_computed: 35,
    symbols_covered: ALL_SYMBOLS.length,
    next_update_in: 120,
  };
});

// ---------------------------------------------------------------------------
// GET /api/ml/models  (list - must come before single-model patterns)
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/ml\/models$/, () => {
  return [
    {
      name: "gradient_boost_v3",
      type: "GBM",
      accuracy: "0.68",
      last_trained: "2h ago",
      features_used: 24,
      auc: 0.72,
    },
    {
      name: "lstm_price_pred",
      type: "LSTM",
      accuracy: "0.62",
      last_trained: "4h ago",
      features_used: 18,
      auc: 0.67,
    },
    {
      name: "random_forest_v2",
      type: "RF",
      accuracy: "0.65",
      last_trained: "1h ago",
      features_used: 30,
      auc: 0.7,
    },
    {
      name: "xgboost_ensemble",
      type: "XGBoost",
      accuracy: "0.71",
      last_trained: "30m ago",
      features_used: 28,
      auc: 0.75,
    },
  ];
});

// ---------------------------------------------------------------------------
// GET /api/ml/models/:name/importance  (must come before any catch-all)
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/ml\/models\/([^/]+)\/importance$/, (path) => {
  const match = path.split("?")[0].match(/^\/api\/ml\/models\/([^/]+)\/importance$/);
  const name = match ? decodeURIComponent(match[1]) : "unknown";
  return {
    model: name,
    features: [
      { name: "rsi_14", importance: 0.142 },
      { name: "macd_signal", importance: 0.118 },
      { name: "news_sentiment_24h", importance: 0.095 },
      { name: "volume_momentum_5d", importance: 0.088 },
      { name: "bollinger_upper", importance: 0.076 },
      { name: "sma_50", importance: 0.072 },
      { name: "atr_14", importance: 0.065 },
      { name: "order_book_imbalance", importance: 0.058 },
      { name: "pe_ratio", importance: 0.052 },
      { name: "fear_greed_index", importance: 0.048 },
    ],
  };
});

// ---------------------------------------------------------------------------
// POST /api/ml/train
// ---------------------------------------------------------------------------
registerRoute("POST", /^\/api\/ml\/train$/, () => {
  return { status: "training_started", estimated_time: "3-5 minutes" };
});

// ---------------------------------------------------------------------------
// GET /api/ml/predictions
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/ml\/predictions$/, () => {
  return {
    AAPL: { direction: "buy", confidence: 0.72, predicted_return: 0.023, horizon: "24h" },
    MSFT: { direction: "buy", confidence: 0.68, predicted_return: 0.018, horizon: "24h" },
    GOOGL: { direction: "hold", confidence: 0.54, predicted_return: 0.005, horizon: "24h" },
    TSLA: { direction: "sell", confidence: 0.61, predicted_return: -0.015, horizon: "24h" },
    NVDA: { direction: "buy", confidence: 0.78, predicted_return: 0.031, horizon: "24h" },
    "BTC/USD": { direction: "buy", confidence: 0.65, predicted_return: 0.028, horizon: "24h" },
    "ETH/USD": { direction: "hold", confidence: 0.52, predicted_return: 0.008, horizon: "24h" },
  };
});
