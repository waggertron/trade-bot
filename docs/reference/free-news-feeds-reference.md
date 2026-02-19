# Free News Feeds & APIs — Complete Reference

## 1. Markets & Finance

### RSS Feeds

| Source | Feed URL | Coverage |
|--------|----------|----------|
| **CNBC Top News** | `https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114` | Breaking financial news |
| **CNBC Markets** | `https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20409666` | Market insider |
| **CNBC Economy** | `https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258` | Economic news |
| **MarketWatch Top** | `https://feeds.marketwatch.com/marketwatch/topstories/` | Stock market news |
| **MarketWatch Pulse** | `https://feeds.marketwatch.com/marketwatch/marketpulse/` | Real-time market pulse |
| **WSJ Markets** | `https://feeds.a.dj.com/rss/RSSMarketsMain.xml` | Headlines + excerpts (paywall) |
| **WSJ Business** | `https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml` | US business news |
| **FT Markets** | `https://www.ft.com/markets?format=rss` | Global markets (paywall) |
| **FT Companies** | `https://www.ft.com/companies?format=rss` | Company news (paywall) |
| **Investing.com Stocks** | `https://www.investing.com/rss/news_25.rss` | Stock market |
| **Investing.com Forex** | `https://www.investing.com/rss/news_1.rss` | Foreign exchange |
| **Investing.com Commodities** | `https://www.investing.com/rss/news_11.rss` | Commodities & futures |
| **Investing.com Economy** | `https://www.investing.com/rss/news_14.rss` | Economic indicators |
| **Investing.com Crypto** | `https://www.investing.com/rss/news_301.rss` | Cryptocurrency |
| **Investing.com Analyst Ratings** | `https://www.investing.com/rss/news_1061.rss` | Stock analyst ratings |
| **Investing.com Most Popular** | `https://www.investing.com/rss/news.rss` | Most popular news |
| **Bloomberg Markets** | `https://feeds.bloomberg.com/markets/news.rss` | Markets (limited availability) |
| **Bloomberg Technology** | `https://feeds.bloomberg.com/technology/news.rss` | Tech (limited availability) |
| **Seeking Alpha** | `https://seekingalpha.com/market_currents.xml` | Market currents |
| **Seeking Alpha per-ticker** | `https://seekingalpha.com/api/sa/combined/AAPL.xml` | Per-symbol (replace AAPL) |
| **Benzinga** | `https://feeds.benzinga.com/benzinga` | Pre/post market movers |
| **Yahoo Finance** | `https://finance.yahoo.com/news/rssindex` | Top financial news |
| **Yahoo per-ticker** | `https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL&region=US&lang=en-US` | Company-specific (replace AAPL) |
| **Motley Fool** | `https://www.fool.com/feeds/index.aspx` | Stock picks, investment education |

### APIs

| Provider | Endpoint | Free Limit | Key Feature |
|----------|----------|-----------|-------------|
| **Finnhub** | `https://finnhub.io/api/v1/news?category=general&token=KEY` | 60 req/min | Best free tier — company news, sentiment, WebSocket |
| **Finnhub Company News** | `https://finnhub.io/api/v1/company-news?symbol=AAPL&from=2025-01-01&to=2025-12-31&token=KEY` | (same) | Per-ticker news |
| **Alpha Vantage** | `https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=AAPL&apikey=KEY` | 25 req/day | AI sentiment scoring on free tier |
| **Polygon.io** | `https://api.polygon.io/v2/reference/news?apiKey=KEY` | 5 req/min | Ticker-tagged news (very limited free) |
| **Tiingo** | `https://api.tiingo.com/tiingo/news?token=KEY` | ~50 symbols/hr | Curated financial news, algorithmically tagged |
| **Benzinga API** | `https://api.benzinga.com/api/v2/news?token=KEY` | Basic via AWS | Headlines + teaser body |
| **EODHD** | `https://eodhd.com/api/news?api_token=KEY&s=AAPL.US` | 20 req/day | Financial news, economic calendar |

### Government Financial Sources (No Auth Required)

| Source | URL/Endpoint | Coverage |
|--------|-------------|----------|
| **SEC EDGAR Submissions** | `https://data.sec.gov/submissions/CIK0000320193.json` | All filings (10 req/sec, User-Agent only) |
| **SEC Company Facts** | `https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json` | Structured XBRL financial data |
| **SEC Full-Text Search** | `https://efts.sec.gov/LATEST/search-index?q="revenue"` | Search all filings |
| **FRED API** | `https://api.stlouisfed.org/fred/series/observations?series_id=GDP&api_key=KEY&file_type=json` | 840K+ economic series (free key, 120 req/min) |
| **Treasury Fiscal Data** | `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny` | Debt, revenue, spending — no key, no limits |
| **Treasury Interest Rates** | `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates` | Average interest rates |
| **Treasury Daily Statement** | `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/dts_table_1` | Daily treasury statement |
| **Treasury Yield Curve** | `https://home.treasury.gov/treasury-daily-interest-rate-xml-feed` | Daily yield curve XML |
| **TreasuryDirect Securities** | `https://www.treasurydirect.gov/TA_WS/securities/search?format=json&type=Bill` | Auction results — no key |
| **NASDAQ Trader** | `https://www.nasdaqtrader.com/trader.aspx?id=newsrss` | Trading halts, listings, alerts |
| **Fed All Press Releases** | `https://www.federalreserve.gov/feeds/press_all.xml` | All Fed press releases |
| **Fed Monetary Policy** | `https://www.federalreserve.gov/feeds/press_monetary.xml` | Monetary policy decisions |
| **Fed Speeches** | `https://www.federalreserve.gov/feeds/speeches.xml` | Fed governor speeches |
| **Fed Testimony** | `https://www.federalreserve.gov/feeds/testimony.xml` | Congressional testimony |
| **Fed Interest Rates (H.15)** | `https://www.federalreserve.gov/feeds/h15.xml` | Selected interest rates |
| **Fed Foreign Exchange (H.10)** | `https://www.federalreserve.gov/feeds/h10.xml` | Exchange rates |
| **Fed Bank Assets (H.8)** | `https://www.federalreserve.gov/feeds/h8.xml` | Assets & liabilities of commercial banks |
| **Fed Reserve Balances (H.4.1)** | `https://www.federalreserve.gov/feeds/h41.xml` | Reserve balances |
| **Fed Industrial Production (G.17)** | `https://www.federalreserve.gov/feeds/g17.xml` | Industrial production & capacity |
| **Fed Consumer Credit (G.19)** | `https://www.federalreserve.gov/feeds/g19.xml` | Consumer credit |
| **Fed Financial Accounts (Z.1)** | `https://www.federalreserve.gov/feeds/z1.xml` | Financial accounts of the US |
| **Fed Policy Rates** | `https://www.federalreserve.gov/feeds/prates.xml` | Policy rates |
| **Fed Working Papers** | `https://www.federalreserve.gov/feeds/working_papers.xml` | Research papers |
| **Fed FEDS Notes** | `https://www.federalreserve.gov/feeds/feds_notes.xml` | Research notes |

---

## 2. Politics

### RSS Feeds

| Source | Feed URL | Coverage |
|--------|----------|----------|
| **AP Politics** | `https://apnews.com/politics.rss` | Breaking US political news |
| **NPR Politics** | `https://feeds.npr.org/1014/rss.xml` | US politics, elections |
| **Politico Congress** | `https://rss.politico.com/congress.xml` | Congressional coverage |
| **Politico White House** | `https://rss.politico.com/white-house.xml` | Executive branch |
| **Politico Playbook** | `https://rss.politico.com/playbook.xml` | Insider morning brief |
| **Politico Defense** | `https://rss.politico.com/defense.xml` | Defense policy |
| **Politico Economy** | `https://rss.politico.com/economy.xml` | Economic policy |
| **Politico Energy** | `https://rss.politico.com/energy.xml` | Energy policy |
| **Politico Healthcare** | `https://rss.politico.com/healthcare.xml` | Healthcare policy |
| **The Hill All News** | `https://thehill.com/news/feed/` | Congress, campaigns |
| **The Hill Policy** | `https://thehill.com/policy/feed/` | Policy reporting |
| **Axios Politics** | `https://api.axios.com/feed/politics` | Smart-brevity political news |
| **White House News** | `https://www.whitehouse.gov/news/feed/` | Presidential statements, EOs |

### APIs

| Provider | Endpoint | Notes |
|----------|----------|-------|
| **Congress.gov API** | `https://api.congress.gov/v3/` | Bills, votes, members, hearings (free key from api.data.gov) |
| **Federal Register API** | `https://www.federalregister.gov/api/v1/` | Rules, EOs, notices since 1994 — **no key required** |
| **GovInfo RSS** | `https://www.govinfo.gov/feeds` | Congressional Record, Federal Register, hearings |

---

## 3. Technology

### RSS Feeds

| Source | Feed URL | Coverage |
|--------|----------|----------|
| **TechCrunch** | `https://techcrunch.com/feed/` | Startups, VC, product launches |
| **TechCrunch AI** | `https://techcrunch.com/category/artificial-intelligence/feed/` | AI/ML specific |
| **TechCrunch Fundings** | `https://techcrunch.com/fundings-exits/feed/` | Fundings & exits |
| **Ars Technica** | `https://feeds.arstechnica.com/arstechnica/index` | In-depth technical reporting |
| **The Verge** | `https://www.theverge.com/rss/index.xml` | Consumer tech, culture |
| **The Verge Tech** | `https://www.theverge.com/rss/tech/index.xml` | Tech section |
| **The Verge Quick Posts** | `https://www.theverge.com/rss/quickposts` | Quick posts |
| **Wired** | `https://www.wired.com/feed/rss` | Tech, science, culture |
| **Hacker News** | `https://news.ycombinator.com/rss` | Developer/startup community |
| **HN Filtered (100+ pts)** | `https://hnrss.org/frontpage?points=100` | High-signal HN stories only |
| **HN Show** | `https://hnrss.org/show` | Show HN posts |
| **HN Ask** | `https://hnrss.org/ask` | Ask HN posts |
| **CNBC Tech** | `https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910` | Tech business news |
| **WSJ Technology** | `https://feeds.a.dj.com/rss/RSSWSJD.xml` | WSJ tech section |

### APIs

| Provider | Endpoint | Notes |
|----------|----------|-------|
| **Hacker News API** | `https://hacker-news.firebaseio.com/v0/topstories.json` | **No key, no rate limit**, real-time |
| **HN New Stories** | `https://hacker-news.firebaseio.com/v0/newstories.json` | Latest submissions |
| **HN Best Stories** | `https://hacker-news.firebaseio.com/v0/beststories.json` | Highest ranked |
| **HN Item Detail** | `https://hacker-news.firebaseio.com/v0/item/{id}.json` | Individual story/comment |

---

## 4. Trade & International

### RSS Feeds

| Source | Feed URL | Coverage |
|--------|----------|----------|
| **WTO News** | `http://www.wto.org/library/rss/latest_news_e.xml` | Trade disputes, tariffs, policy reviews |
| **AP Business** | `https://apnews.com/business.rss` | International business/trade |
| **AP World** | `https://apnews.com/world-news.rss` | Global affairs |
| **Supply Chain Dive** | `https://www.supplychaindive.com/feeds/news/` | Logistics, tariffs, freight |
| **Politico Economy** | `https://rss.politico.com/economy.xml` | Trade policy coverage |
| **Reuters Business** | `https://www.reutersagency.com/feed/?best-topics=business-finance` | Global business (reliability varies) |

### APIs

| Provider | Endpoint | Notes |
|----------|----------|-------|
| **Federal Register (trade)** | `https://www.federalregister.gov/api/v1/documents.json?conditions[agencies][]=international-trade-commission` | Tariff changes, anti-dumping — **no key** |
| **Congress.gov (trade bills)** | `https://api.congress.gov/v3/bill?query=trade` | Trade legislation (free key) |
| **GDELT Project** | `https://api.gdeltproject.org/api/v2/doc/doc` | Global news 100+ languages — **no key, no limit** |
| **Regulations.gov** | `https://api.regulations.gov/v4/` | Public comments on trade rules (free key) |
| **USITC EDIS** | `https://edis.usitc.gov/external/rss/rssFeedGenerator.html` | ITC investigations, tariff schedules |

---

## 5. Industry / Sector-Specific

### RSS Feeds

| Source | Feed URL | Sector |
|--------|----------|--------|
| **EIA Today in Energy** | `https://www.eia.gov/rss/todayinenergy.xml` | Energy |
| **Defense News** | `https://www.defensenews.com/m/rss/` | Defense/military |
| **Defense One** | `https://www.defenseone.com/rss/all/` | National security |
| **RealClearDefense** | `https://www.realcleardefense.com/index.xml` | Defense commentary |
| **Fierce Healthcare** | `https://www.fiercehealthcare.com/rss/xml` | Healthcare business |
| **Healthcare Dive** | `https://www.healthcaredive.com/feeds/news/` | Healthcare industry |
| **Manufacturing Dive** | `https://www.manufacturingdive.com/feeds/news/` | Manufacturing |
| **Engineering News-Record** | `https://www.enr.com/rss` | Construction, infrastructure |

### APIs

| Provider | Endpoint | Notes |
|----------|----------|-------|
| **EIA API** | `https://api.eia.gov/v2/` | 1M+ energy data series (free key) |

---

## 6. Media & Journalism

### RSS Feeds

| Source | Feed URL | Coverage |
|--------|----------|----------|
| **Nieman Lab** | `https://www.niemanlab.org/feed/` | Future of journalism, media innovation |
| **Columbia Journalism Review** | `https://www.cjr.org/feed` | Media criticism, press freedom |
| **Poynter** | `https://www.poynter.org/feed/` | Journalism ethics, fact-checking |
| **Press Gazette** | `https://pressgazette.co.uk/feed/` | International journalism industry |
| **Digiday** | `https://digiday.com/feed/` | Digital media, ad tech, platforms |
| **Adweek** | `https://www.adweek.com/feed/` | Advertising, marketing, media buying |
| **Variety** | `https://variety.com/feed/` | Entertainment industry |
| **Hollywood Reporter** | `https://www.hollywoodreporter.com/feed/` | Film, TV, media business |
| **Axios Media** | `https://api.axios.com/feed/media-deals` | Media deals and trends |

---

## Cross-Category Power Tools

| Tool | Endpoint | Coverage | Auth |
|------|----------|----------|------|
| **GDELT** | `https://api.gdeltproject.org/api/v2/doc/doc` | ALL global news, 100+ languages, updated every 15 min, back to 1979 | None |
| **NewsAPI.org** | `https://newsapi.org/v2/everything?q=QUERY&apiKey=KEY` | 150K+ sources, filter by category/keyword | 100 req/day (dev only) |
| **GNews** | `https://gnews.io/api/v4/top-headlines?category=business&token=KEY` | 60K+ sources, 22 languages | 100 req/day (dev only) |
| **NewsData.io** | `https://newsdata.io/api/1/latest?apikey=KEY&category=business` | 85K+ sources, financial sentiment | 200 credits/day (commercial OK) |
| **Mediastack** | `http://api.mediastack.com/v1/news?access_key=KEY&categories=business` | 7.5K+ sources, 50+ countries | 100 req/month (no HTTPS on free) |
| **Finlight.me** | `https://api.finlight.me/v1/articles?token=KEY` | Financial/geopolitical, ticker-tagged | 5K req/month |
| **Federal Register** | `https://www.federalregister.gov/api/v1/` | All US federal rulemaking since 1994 | None |

---

## Quick Comparison: Best Free Source Per Category

| Category | Best RSS | Best API |
|----------|----------|----------|
| **Markets** | Investing.com (7+ feeds, reliable) | Finnhub (60 req/min) |
| **Politics** | Politico (8 topic feeds) | Congress.gov API |
| **Technology** | TechCrunch + Hacker News | HN Firebase API (no limits) |
| **Trade** | Supply Chain Dive + WTO | GDELT (no key, no limit) |
| **Industry** | EIA + sector Dive sites | EIA API (1M+ series) |
| **Media** | Nieman Lab + Digiday | GDELT (query for media topics) |
| **Economic Data** | Fed RSS (30+ feeds) | FRED (840K+ series, 120 req/min) |
| **Government** | GovInfo | Federal Register API (no key) |

## Rate Limits at a Glance

| Provider | Free Limit | Auth Required |
|----------|-----------|---------------|
| Finnhub | 60/min | Yes (API key) |
| Alpha Vantage | 25/day | Yes (API key) |
| Polygon.io | 5/min | Yes (API key) |
| NewsAPI.org | 100/day | Yes (API key) |
| GNews | 100/day | Yes (API key) |
| NewsData.io | 200 credits/day | Yes (API key) |
| Mediastack | 100/month | Yes (API key) |
| Finlight.me | 5,000/month | Yes (API key) |
| EODHD | 20/day | Yes (API key) |
| FRED | 120/min | Yes (API key) |
| SEC EDGAR | 10/sec | No (User-Agent only) |
| Treasury Fiscal Data | No limit | No |
| Hacker News API | No limit | No |
| GDELT | No limit | No |
| Federal Register | No limit | No |
| All RSS feeds | No limit | No |
