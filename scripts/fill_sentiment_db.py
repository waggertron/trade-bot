"""
Fill the production DB with articles from all free RSS/government feeds,
then score them with Ollama.

Usage:
    uv run python scripts/fill_sentiment_db.py

Uses trade_bot.db (the production database). Safe to re-run — already-fetched
articles and already-scored articles are skipped automatically.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.db.database import Database
from src.db.models import ArticleRecord, SentimentScoreRecord
from src.db.seed_feeds import seed_feeds_from_reference
from src.providers.configs import OllamaSentimentConfig, RSSConfig
from src.providers.government import GovernmentFeedAdapter
from src.providers.ollama_sentiment import OllamaSentimentAnalyzer
from src.providers.rss import RSSNewsProvider

# Symbols to tag every article with (used for sentiment lookups by symbol)
SYMBOLS = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN", "META", "TSLA", "BTC", "ETH", "SPY"]

# Max concurrent feed fetches
FETCH_CONCURRENCY = 8

DB_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///trade_bot.db")


async def seed_if_needed(db: Database) -> int:
    count = await db.count_feeds()
    if count == 0:
        print("[feeds] Seeding feeds from reference doc...")
        n = await seed_feeds_from_reference(db)
        print(f"[feeds] Seeded {n} feeds")
        return n
    print(f"[feeds] {count} feeds already in DB")
    return count


async def fetch_feed(feed, symbols: list[str]) -> list[ArticleRecord]:
    """Fetch one feed and return ArticleRecord objects."""
    try:
        if feed.feed_type == "rss":
            provider = RSSNewsProvider(RSSConfig(feed_urls=[feed.url], max_articles_per_fetch=50))
        elif feed.feed_type == "government":
            provider = GovernmentFeedAdapter([feed])
        else:
            return []

        articles = await provider.fetch_articles("SPY", limit=50)
        records = []
        for a in articles:
            records.append(ArticleRecord(
                content_hash=a.content_hash,
                title=a.title,
                body=a.body,
                source=a.source or feed.name,
                url=a.url,
                published_at=a.published_at,
                symbols=symbols,
            ))
        return records
    except Exception as e:
        print(f"  [warn] {feed.name}: {type(e).__name__}: {e}")
        return []


async def fetch_all_feeds(db: Database, symbols: list[str]) -> int:
    """Fetch all free (no API key) RSS and government feeds concurrently."""
    feeds = await db.list_feeds(enabled_only=True)
    free_feeds = [f for f in feeds if f.auth_type == "free" and f.feed_type in ("rss", "government")]

    print(f"\n[fetch] {len(free_feeds)} free feeds to pull from ({len(feeds) - len(free_feeds)} api_key feeds skipped)")

    semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)
    total_new = 0
    total_dup = 0
    done = 0

    async def fetch_and_save(feed):
        nonlocal total_new, total_dup, done
        async with semaphore:
            records = await fetch_feed(feed, symbols)
            new = 0
            for rec in records:
                result = await db.save_article(rec)
                if result is not None:
                    new += 1
                    total_new += 1
                else:
                    total_dup += 1
            done += 1
            if new > 0:
                print(f"  [{done:3}/{len(free_feeds)}] {feed.name:<40} +{new} articles")
            else:
                print(f"  [{done:3}/{len(free_feeds)}] {feed.name:<40} (no new)")
            return new

    await asyncio.gather(*[fetch_and_save(f) for f in free_feeds])
    return total_new


async def score_all(db: Database, analyzer: OllamaSentimentAnalyzer, symbols: list[str]) -> int:
    """Score all unscored articles for all symbols."""
    print(f"\n[score] Checking for unscored articles across {len(symbols)} symbols...")

    # Collect unique unscored article IDs across all symbols
    seen_ids: set[str] = set()
    to_score: list[ArticleRecord] = []
    for symbol in symbols:
        unscored = await db.get_unscored_articles(symbol, analyzer.name, limit=2000)
        for a in unscored:
            if a.id not in seen_ids:
                seen_ids.add(a.id)
                to_score.append(a)

    if not to_score:
        print("[score] All articles already scored — nothing to do.")
        return 0

    print(f"[score] {len(to_score)} articles to score with {analyzer.name}")
    print(f"[score] Estimated time: ~{len(to_score) * 2 // 60}–{len(to_score) * 4 // 60} min\n")

    scored = 0
    t0 = time.time()

    for i, article in enumerate(to_score, 1):
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

        elapsed = time.time() - t0
        rate = scored / elapsed
        remaining = (len(to_score) - i) / rate if rate > 0 else 0

        bar = _bar(result.score)
        eta = f"{int(remaining // 60)}m{int(remaining % 60):02d}s"
        print(
            f"  [{i:4}/{len(to_score)}] {bar} {result.score:+.2f}  "
            f"ETA {eta}  {article.title[:55]}"
        )

    return scored


async def print_summary(db: Database, analyzer: OllamaSentimentAnalyzer, symbols: list[str]) -> None:
    print(f"\n{'='*65}")
    print("SUMMARY")
    print(f"{'='*65}")

    all_scores = await db.load_recent_scores(hours=48 * 30)
    if not all_scores:
        print("  No scores in DB yet.")
        return

    avg = sum(s.score for s in all_scores) / len(all_scores)
    bullish = sum(1 for s in all_scores if s.score > 0.1)
    bearish = sum(1 for s in all_scores if s.score < -0.1)
    neutral = len(all_scores) - bullish - bearish

    print(f"  Total articles scored : {len(all_scores)}")
    print(f"  Avg sentiment         : {avg:+.3f}")
    print(f"  Bullish (>0.1)        : {bullish}")
    print(f"  Neutral               : {neutral}")
    print(f"  Bearish (<-0.1)       : {bearish}")
    print()

    # Per-symbol breakdown
    print("  Per-symbol (from recent scores):")
    for symbol in symbols[:6]:
        unscored = await db.get_articles_for_symbol(symbol, limit=1000)
        if not unscored:
            continue
        # Get scores for this symbol
        scored_ids = {a.id for a in unscored}
        sym_scores = [s for s in all_scores if s.article_id in scored_ids]
        if not sym_scores:
            continue
        sym_avg = sum(s.score for s in sym_scores) / len(sym_scores)
        bar = _bar(sym_avg)
        print(f"    {bar} {symbol:<6} {sym_avg:+.3f}  ({len(sym_scores)} articles)")


def _bar(score: float) -> str:
    if score > 0.3:   return "🟢"
    if score > 0.05:  return "🔵"
    if score < -0.3:  return "🔴"
    if score < -0.05: return "🟠"
    return "⚪"


async def main() -> None:
    print(f"\n{'='*65}")
    print("Sentiment DB Fill — RSS + Government feeds → Ollama llama3.2")
    print(f"{'='*65}\n")

    db = Database(DB_URL)
    await db.initialize()
    print(f"[db] {DB_URL}")

    await seed_if_needed(db)
    new_articles = await fetch_all_feeds(db, SYMBOLS)
    print(f"\n[fetch] Done. {new_articles} new articles saved to DB.")

    analyzer = OllamaSentimentAnalyzer(OllamaSentimentConfig(model="llama3.2"))
    scored = await score_all(db, analyzer, SYMBOLS)
    print(f"\n[score] Done. {scored} articles scored.")

    await print_summary(db, analyzer, SYMBOLS)
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
