import { registerRoute } from "../router";
import { seededRandom } from "../generators";
import { ALL_SYMBOLS, NEWS_SOURCES } from "./constants";

// ---------------------------------------------------------------------------
// Headlines & summaries
// ---------------------------------------------------------------------------
const HEADLINES: { title: string; summary: string }[] = [
  {
    title: "AAPL Reports Record Q4 Revenue, Beating Wall Street Estimates",
    summary:
      "Apple posted quarterly revenue of $94.8 billion, surpassing analyst expectations by nearly 3%. Strong iPhone and Services growth drove the beat as the company navigated a challenging macro environment.",
  },
  {
    title: "Bitcoin Surges Past $97,000 as Institutional Demand Grows",
    summary:
      "Bitcoin reached a new all-time high above $97,000, fueled by sustained inflows from institutional investors. Analysts point to spot ETF demand and a weakening dollar as key catalysts for the rally.",
  },
  {
    title: "NVIDIA's AI Chip Demand Drives 200% Revenue Growth",
    summary:
      "NVIDIA reported fiscal-quarter revenue growth of over 200%, powered by insatiable demand for its data-center GPUs. The company raised forward guidance, citing a multi-year AI infrastructure build-out cycle.",
  },
  {
    title: "Fed Minutes Signal Cautious Approach to Rate Cuts",
    summary:
      "Minutes from the latest FOMC meeting revealed officials remain divided on the pace of future rate reductions. Markets adjusted expectations, now pricing in fewer cuts through year-end.",
  },
  {
    title: "Tesla Announces New Model, Stock Rallies 5%",
    summary:
      "Tesla unveiled its next-generation compact EV at a live event, targeting a sub-$30,000 price point. Shares jumped 5% in after-hours trading as investors cheered the mass-market push.",
  },
  {
    title: "Microsoft Cloud Revenue Exceeds Expectations in Latest Quarter",
    summary:
      "Microsoft's Intelligent Cloud segment delivered $28.5 billion in revenue, beating consensus by 4%. Azure growth re-accelerated to 33%, driven by AI workload adoption across enterprise customers.",
  },
  {
    title: "Ethereum Network Upgrade Completes Successfully",
    summary:
      "The long-awaited Ethereum protocol upgrade went live without incident, reducing transaction fees by an estimated 40%. On-chain activity surged in the hours following the upgrade as developers tested new features.",
  },
  {
    title: "Meta Platforms Expands AI Infrastructure Investment",
    summary:
      "Meta announced plans to invest an additional $15 billion in AI data centers over the next two years. The company said the spending is essential to support its generative-AI products and advertising platform.",
  },
  {
    title: "Amazon Web Services Launches New AI Services for Enterprise",
    summary:
      "AWS introduced a suite of managed AI services aimed at enterprise customers, including a fine-tuning platform and inference optimization tools. The launch intensifies competition with Microsoft Azure and Google Cloud.",
  },
  {
    title: "Solana Network Sets New Transaction Record",
    summary:
      "Solana processed over 65 million transactions in a single day, setting a new network record. The milestone comes amid growing DeFi and NFT activity on the high-throughput blockchain.",
  },
  {
    title: "Google DeepMind Breakthrough Boosts Alphabet Stock",
    summary:
      "Alphabet shares climbed 4% after Google DeepMind published research on a new foundation model that outperforms existing benchmarks. Investors see the advance as strengthening Google's competitive position in AI.",
  },
  {
    title: "Market Volatility Increases Amid Geopolitical Tensions",
    summary:
      "The VIX spiked to a three-month high as escalating geopolitical conflicts rattled global markets. Safe-haven assets including gold and the US dollar rallied while equities sold off broadly.",
  },
  {
    title: "Crypto Markets See $2B in Inflows This Week",
    summary:
      "Digital-asset investment products attracted $2 billion in net inflows, the largest weekly total this year. Bitcoin and Ethereum funds accounted for the majority of the capital movement.",
  },
  {
    title: "TSLA Short Interest Drops to Lowest Level in 2 Years",
    summary:
      "Short interest in Tesla shares fell to 2.8% of the float, the lowest reading since early 2024. Analysts attribute the decline to improving delivery numbers and a more favorable regulatory outlook.",
  },
  {
    title: "Tech Sector Leads S&P 500 to New All-Time High",
    summary:
      "The S&P 500 closed at a record high, propelled by broad-based strength in technology stocks. Mega-cap names including Apple, Microsoft, and NVIDIA contributed the largest index-point gains.",
  },
  {
    title: "NVDA Partners with Major Cloud Providers for AI Expansion",
    summary:
      "NVIDIA deepened partnerships with AWS, Azure, and Google Cloud to accelerate AI infrastructure deployment. The collaboration includes co-engineered solutions optimized for the latest Blackwell GPU architecture.",
  },
  {
    title: "Bitcoin ETF Sees Record Daily Volume",
    summary:
      "Spot Bitcoin ETFs recorded their highest single-day trading volume since launch, exceeding $4.6 billion. The surge coincided with Bitcoin's push toward the $100,000 psychological level.",
  },
  {
    title: "Retail Investor Sentiment Turns Bullish on Growth Stocks",
    summary:
      "Survey data shows retail investors are the most optimistic on growth stocks in over a year. Increased allocation to technology and crypto assets reflects renewed risk appetite among individual traders.",
  },
  {
    title: "Supply Chain Improvements Boost Manufacturing Sector",
    summary:
      "The ISM Manufacturing Index rose to 52.4, signaling expansion for the second consecutive month. Companies reported shorter lead times and lower input costs as global supply chains continue to normalize.",
  },
  {
    title: "Central Bank Digital Currencies Gain Momentum Globally",
    summary:
      "More than 130 countries are now exploring or piloting central bank digital currencies, according to a new BIS report. The trend is accelerating as policymakers seek to modernize payment infrastructure.",
  },
];

// ---------------------------------------------------------------------------
// Generate 50 mock articles using seededRandom(555)
// ---------------------------------------------------------------------------
interface NewsArticle {
  title: string;
  summary: string;
  symbol: string;
  source: string;
  sentiment_score: number;
  timestamp: string;
  url: string;
}

const rng = seededRandom(555);
const now = Date.now();
const FORTY_EIGHT_HOURS = 48 * 60 * 60 * 1000;

const articles: NewsArticle[] = Array.from({ length: 50 }, (_, i) => {
  const headline = HEADLINES[i % HEADLINES.length];
  const symbol = ALL_SYMBOLS[Math.floor(rng() * ALL_SYMBOLS.length)];
  const source = NEWS_SOURCES[Math.floor(rng() * NEWS_SOURCES.length)];
  const sentiment_score = Math.round((rng() * 2 - 1) * 100) / 100; // -1.0 to 1.0
  const offset = Math.floor(rng() * FORTY_EIGHT_HOURS);
  const timestamp = new Date(now - offset).toISOString();

  return {
    title: headline.title,
    summary: headline.summary,
    symbol,
    source,
    sentiment_score,
    timestamp,
    url: "#",
  };
});

// Sort newest first
articles.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

// ---------------------------------------------------------------------------
// GET /api/news/articles
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/news\/articles$/, (path) => {
  const params = new URLSearchParams(path.split("?")[1] ?? "");
  const symbolFilter = params.get("symbol");
  const sourceFilter = params.get("source");
  const limit = parseInt(params.get("limit") ?? "25", 10);

  let filtered = articles;

  if (symbolFilter) {
    filtered = filtered.filter((a) => a.symbol === symbolFilter);
  }
  if (sourceFilter) {
    filtered = filtered.filter((a) => a.source === sourceFilter);
  }

  return filtered.slice(0, limit);
});

// ---------------------------------------------------------------------------
// GET /api/news/status
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/news\/status$/, () => {
  return {
    providers: [
      { name: "Bloomberg", healthy: true, articles_today: 23 },
      { name: "Reuters", healthy: true, articles_today: 18 },
      { name: "CoinDesk", healthy: true, articles_today: 31 },
      { name: "CNBC", healthy: false, articles_today: 0 },
    ],
  };
});

// ---------------------------------------------------------------------------
// GET /api/news/feeds
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/news\/feeds$/, () => {
  return {
    providers: [
      { name: "Bloomberg", healthy: true, articles_today: 23 },
      { name: "Reuters", healthy: true, articles_today: 18 },
      { name: "CoinDesk", healthy: true, articles_today: 31 },
      { name: "CNBC", healthy: false, articles_today: 0 },
    ],
  };
});

// ---------------------------------------------------------------------------
// GET /api/sentiment/aggregate
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/sentiment\/aggregate$/, () => {
  return {
    AAPL: { score: 0.42, articles: 8 },
    MSFT: { score: 0.35, articles: 6 },
    GOOGL: { score: 0.28, articles: 5 },
    AMZN: { score: 0.15, articles: 4 },
    TSLA: { score: -0.12, articles: 7 },
    NVDA: { score: 0.65, articles: 9 },
    META: { score: 0.22, articles: 3 },
    "BTC/USD": { score: 0.55, articles: 12 },
    "ETH/USD": { score: 0.38, articles: 6 },
    "SOL/USD": { score: 0.18, articles: 4 },
  };
});

// ---------------------------------------------------------------------------
// GET /api/sentiment/trend
// ---------------------------------------------------------------------------
registerRoute("GET", /^\/api\/sentiment\/trend$/, (path) => {
  const params = new URLSearchParams(path.split("?")[1] ?? "");
  const symbol = params.get("symbol") ?? "AAPL";
  const period = params.get("period") ?? "7d";

  const trendRng = seededRandom(
    symbol.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0),
  );

  const days = period === "30d" ? 30 : period === "14d" ? 14 : 7;
  const step = days / 7;
  const points: { date: string; score: number }[] = [];

  for (let i = 6; i >= 0; i--) {
    const date = new Date(now - i * step * 24 * 60 * 60 * 1000);
    const score = Math.round((trendRng() * 2 - 1) * 100) / 100;
    points.push({
      date: date.toISOString().split("T")[0],
      score,
    });
  }

  return { points };
});
