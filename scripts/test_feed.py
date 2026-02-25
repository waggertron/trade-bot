"""
Quick test: fetch articles from CNBC Top News RSS and score with Ollama.

Usage:
    uv run python scripts/test_feed.py

Creates a local test DB at /tmp/test_feed.db (safe to delete).
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import Database
from src.db.models import ArticleRecord
from src.providers.configs import OllamaSentimentConfig
from src.providers.ollama_sentiment import OllamaSentimentAnalyzer
from src.providers.rss import RSSNewsProvider
from src.providers.configs import RSSConfig
from src.db.models import SentimentScoreRecord


FEED_URL = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"
DB_PATH = "/tmp/test_feed.db"
SYMBOLS = ["AAPL", "MSFT", "BTC", "SPY"]  # Tags every article with these for demo


async def main() -> None:
    print(f"\n{'='*60}")
    print("Feed Test: CNBC Top News → Ollama llama3.2")
    print(f"{'='*60}\n")

    # 1. Set up DB
    db = Database(f"sqlite+aiosqlite:///{DB_PATH}")
    await db.initialize()
    print(f"[DB] Initialized at {DB_PATH}")

    # 2. Fetch articles from CNBC RSS
    provider = RSSNewsProvider(RSSConfig(feed_urls=[FEED_URL], max_articles_per_fetch=50))
    print(f"\n[RSS] Fetching from CNBC Top News...")
    raw_articles = await provider.fetch_articles("SPY", limit=50)
    print(f"[RSS] Got {len(raw_articles)} articles from feed")

    # 3. Save to DB (deduplicated by content_hash)
    new_count = 0
    saved_articles: list[ArticleRecord] = []
    for article in raw_articles:
        record = ArticleRecord(
            content_hash=article.content_hash,
            title=article.title,
            body=article.body,
            source=article.source,
            url=article.url,
            published_at=article.published_at,
            symbols=SYMBOLS,
        )
        result = await db.save_article(record)
        if result is not None:
            new_count += 1
            saved_articles.append(record)
        else:
            # Already in DB — reload it
            existing = await db.get_articles_for_symbol("SPY", limit=1000)
            saved_articles = existing
            break

    if not saved_articles:
        saved_articles = await db.get_articles_for_symbol("SPY", limit=100)

    print(f"[DB] {new_count} new articles saved ({len(raw_articles) - new_count} duplicates skipped)")

    # Print article list
    print(f"\n{'─'*60}")
    print("ARTICLES IN DB:")
    print(f"{'─'*60}")
    for i, a in enumerate(saved_articles[:20], 1):
        pub = a.published_at.strftime("%b %d %H:%M") if a.published_at else "unknown"
        print(f"  {i:2}. [{pub}] {a.title[:70]}")

    # 4. Score with Ollama
    analyzer = OllamaSentimentAnalyzer(OllamaSentimentConfig(model="llama3.2"))
    print(f"\n{'─'*60}")
    print(f"SCORING {len(saved_articles)} ARTICLES WITH {analyzer.name}...")
    print(f"{'─'*60}")

    scored = 0
    skipped = 0
    for article in saved_articles:
        if await db.has_score(article.id, analyzer.name):
            skipped += 1
            continue

        text = f"{article.title}. {article.body}"
        result = await analyzer.score(text)

        score_rec = SentimentScoreRecord(
            article_id=article.id,
            score=result.score,
            magnitude=result.magnitude,
            reasoning=result.reasoning,
            analyzer=analyzer.name,
        )
        await db.save_score(score_rec)
        scored += 1

        bar = _score_bar(result.score)
        print(f"  {bar} {result.score:+.2f} (mag={result.magnitude:.2f})  {article.title[:55]}")

    if skipped:
        print(f"  [skipped {skipped} already-scored articles]")

    # 5. Summary
    all_scores = await db.load_recent_scores(hours=48 * 7)
    if all_scores:
        avg = sum(s.score for s in all_scores) / len(all_scores)
        bullish = sum(1 for s in all_scores if s.score > 0.1)
        bearish = sum(1 for s in all_scores if s.score < -0.1)
        neutral = len(all_scores) - bullish - bearish

        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"  Total scored:  {len(all_scores)}")
        print(f"  Avg sentiment: {avg:+.3f}")
        print(f"  Bullish (>0.1): {bullish}")
        print(f"  Neutral:        {neutral}")
        print(f"  Bearish (<-0.1): {bearish}")
        print(f"\n  DB saved at: {DB_PATH}")
        print(f"  Re-run to skip already-scored articles (Ollama won't be called again)\n")

    await db.close()


def _score_bar(score: float) -> str:
    """Simple colored indicator."""
    if score > 0.3:
        return "🟢"
    elif score > 0.05:
        return "🔵"
    elif score < -0.3:
        return "🔴"
    elif score < -0.05:
        return "🟠"
    else:
        return "⚪"


if __name__ == "__main__":
    asyncio.run(main())
