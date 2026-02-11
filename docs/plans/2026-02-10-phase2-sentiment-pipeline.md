# Phase 2: Sentiment Analysis Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a multi-stage sentiment pipeline: fetch articles from news providers, deduplicate/buffer, score with sentiment analyzers, aggregate into rolling per-symbol scores, persist to DB, and feed the existing SentimentStrategy with real data.

**Architecture:** NewsProviders fetch articles → ArticleBuffer deduplicates → SentimentAnalyzer scores each article → SentimentAggregator computes time-weighted rolling scores → SentimentStore persists articles + scores to DB → SentimentStrategy consumes aggregated scores.

**Tech Stack:** Python 3.12+, Pydantic v2, asyncio, aiosqlite/SQLAlchemy, feedparser (RSS), httpx, Typer CLI

---

### Task 1: Define Article Model + Move SentimentResult to Shared Models

**Why:** Currently `NewsProvider.fetch_articles()` returns `list[Any]` and `SentimentResult` lives in `mock.py`. Both need to be proper shared Pydantic models that all components reference.

**Files:**
- Create: `src/sentiment/__init__.py`
- Create: `src/sentiment/models.py`
- Modify: `src/providers/protocols.py` — update `NewsProvider.fetch_articles` return type and `SentimentAnalyzer.score` return type
- Modify: `src/providers/mock.py` — import `SentimentResult` from new location, remove local definition
- Test: `tests/unit/sentiment/test_models.py`

**Step 1: Write failing tests**

```python
# tests/unit/sentiment/__init__.py  (empty)
# tests/unit/sentiment/test_models.py

import pytest
from datetime import datetime, timezone


class TestArticle:
    def test_creates_with_required_fields(self):
        from src.sentiment.models import Article

        article = Article(
            title="Bitcoin hits new high",
            body="BTC surged past $100k today...",
            source="rss",
            url="https://example.com/btc",
            published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            related_symbols=["BTC"],
        )
        assert article.title == "Bitcoin hits new high"
        assert article.source == "rss"
        assert article.related_symbols == ["BTC"]
        assert article.id  # auto-generated

    def test_auto_generates_content_hash(self):
        from src.sentiment.models import Article

        a = Article(
            title="Test",
            body="Body text",
            source="rss",
            url="https://example.com",
            published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            related_symbols=["AAPL"],
        )
        assert a.content_hash  # auto-generated from title+body
        assert isinstance(a.content_hash, str)

    def test_same_content_same_hash(self):
        from src.sentiment.models import Article

        kwargs = dict(
            title="Same Title",
            body="Same Body",
            source="rss",
            url="https://example.com",
            published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            related_symbols=["AAPL"],
        )
        a1 = Article(**kwargs)
        a2 = Article(**kwargs)
        assert a1.content_hash == a2.content_hash

    def test_different_content_different_hash(self):
        from src.sentiment.models import Article

        base = dict(
            source="rss",
            url="https://example.com",
            published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            related_symbols=["AAPL"],
        )
        a1 = Article(title="Title A", body="Body A", **base)
        a2 = Article(title="Title B", body="Body B", **base)
        assert a1.content_hash != a2.content_hash

    def test_frozen(self):
        from src.sentiment.models import Article

        a = Article(
            title="Test",
            body="Body",
            source="rss",
            url="https://example.com",
            published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            related_symbols=["AAPL"],
        )
        with pytest.raises(Exception):
            a.title = "Modified"

    def test_serialization_roundtrip(self):
        from src.sentiment.models import Article

        a = Article(
            title="Test",
            body="Body",
            source="rss",
            url="https://example.com",
            published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            related_symbols=["AAPL"],
        )
        data = a.model_dump()
        a2 = Article.model_validate(data)
        assert a2.title == a.title
        assert a2.content_hash == a.content_hash


class TestSentimentResult:
    """SentimentResult already exists in mock.py — verify it works from new location."""

    def test_imports_from_sentiment_models(self):
        from src.sentiment.models import SentimentResult

        result = SentimentResult(
            score=0.8,
            magnitude=0.6,
            timestamp=datetime.now(timezone.utc),
        )
        assert result.score == 0.8

    def test_rejects_out_of_range(self):
        from src.sentiment.models import SentimentResult

        with pytest.raises(Exception):
            SentimentResult(score=1.5, magnitude=0.5, timestamp=datetime.now(timezone.utc))
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/sentiment/test_models.py -v`
Expected: FAIL — module not found

**Step 3: Implement**

Create `src/sentiment/__init__.py` (empty).

Create `src/sentiment/models.py`:
```python
"""Shared Pydantic models for the sentiment pipeline."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Article(BaseModel):
    """A news article fetched from a provider."""
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    title: str
    body: str = ""
    source: str  # e.g., "rss", "reddit", "newsapi"
    url: str = ""
    published_at: datetime
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    related_symbols: list[str] = Field(default_factory=list)
    content_hash: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.content_hash:
            h = hashlib.sha256(
                (self.title + self.body[:200]).encode()
            ).hexdigest()
            object.__setattr__(self, "content_hash", h)


class SentimentResult(BaseModel):
    """Result from scoring an article's sentiment."""
    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=-1, le=1)
    magnitude: float = Field(ge=0, le=1)
    timestamp: datetime
    reasoning: str | None = None
    article_id: str | None = None
    analyzer: str | None = None
```

Then update `src/providers/mock.py`: remove the local `SentimentResult` class and import from `src.sentiment.models`. Update `src/providers/protocols.py`: change `fetch_articles` return type from `list[Any]` to `list[Article]` (import Article from src.sentiment.models), and `score`/`score_batch` return types to use `SentimentResult`.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/sentiment/test_models.py tests/unit/providers/ tests/test_models.py -v`
Expected: ALL PASS (no regressions)

**Step 5: Commit**

```bash
git add src/sentiment/ tests/unit/sentiment/ src/providers/protocols.py src/providers/mock.py
git commit -m "feat: add Article and SentimentResult shared models for sentiment pipeline"
```

---

### Task 2: ArticleBuffer — Dedup and Queue

**Why:** Multiple news providers may return the same article. The buffer deduplicates by content hash and queues articles by symbol for downstream scoring.

**Files:**
- Create: `src/sentiment/article_buffer.py`
- Test: `tests/unit/sentiment/test_article_buffer.py`

**Step 1: Write failing tests**

```python
# tests/unit/sentiment/test_article_buffer.py
import pytest
from datetime import datetime, timedelta, timezone

from src.sentiment.models import Article


def _make_article(title="Test", body="Body", symbol="AAPL", **kwargs):
    return Article(
        title=title,
        body=body,
        source="test",
        url="https://example.com",
        published_at=datetime.now(timezone.utc),
        related_symbols=[symbol],
        **kwargs,
    )


class TestArticleBuffer:
    def test_ingest_new_articles(self):
        from src.sentiment.article_buffer import ArticleBuffer
        buf = ArticleBuffer()
        count = buf.ingest([_make_article(title="A"), _make_article(title="B")])
        assert count == 2

    def test_dedup_same_content(self):
        from src.sentiment.article_buffer import ArticleBuffer
        buf = ArticleBuffer()
        a = _make_article(title="Same", body="Same body")
        count1 = buf.ingest([a])
        count2 = buf.ingest([a])  # same content_hash
        assert count1 == 1
        assert count2 == 0

    def test_drain_returns_and_clears(self):
        from src.sentiment.article_buffer import ArticleBuffer
        buf = ArticleBuffer()
        buf.ingest([_make_article(symbol="AAPL")])
        articles = buf.drain("AAPL")
        assert len(articles) == 1
        assert buf.drain("AAPL") == []  # cleared

    def test_multi_symbol_article_queued_to_each(self):
        from src.sentiment.article_buffer import ArticleBuffer
        buf = ArticleBuffer()
        a = Article(
            title="Multi",
            body="Body",
            source="test",
            url="https://example.com",
            published_at=datetime.now(timezone.utc),
            related_symbols=["AAPL", "GOOG"],
        )
        buf.ingest([a])
        assert len(buf.drain("AAPL")) == 1
        assert len(buf.drain("GOOG")) == 1

    def test_expire_old_hashes(self):
        from src.sentiment.article_buffer import ArticleBuffer
        buf = ArticleBuffer(max_age=timedelta(seconds=0))
        a = _make_article(title="Old")
        buf.ingest([a])
        buf.expire()
        # After expiry, same hash should be accepted again
        count = buf.ingest([a])
        assert count == 1

    def test_symbols_returns_queued_symbols(self):
        from src.sentiment.article_buffer import ArticleBuffer
        buf = ArticleBuffer()
        buf.ingest([_make_article(symbol="AAPL"), _make_article(symbol="GOOG", title="G")])
        assert set(buf.symbols()) == {"AAPL", "GOOG"}

    def test_pending_count(self):
        from src.sentiment.article_buffer import ArticleBuffer
        buf = ArticleBuffer()
        buf.ingest([_make_article(symbol="AAPL"), _make_article(symbol="AAPL", title="B")])
        assert buf.pending_count("AAPL") == 2
        assert buf.pending_count("GOOG") == 0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/sentiment/test_article_buffer.py -v`
Expected: FAIL — module not found

**Step 3: Implement**

Create `src/sentiment/article_buffer.py`:
```python
"""Deduplicates and queues articles by symbol."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from src.sentiment.models import Article


class ArticleBuffer:
    def __init__(self, max_age: timedelta = timedelta(hours=24)) -> None:
        self._seen: dict[str, datetime] = {}  # content_hash -> first_seen
        self._queue: dict[str, list[Article]] = defaultdict(list)
        self._max_age = max_age

    def ingest(self, articles: list[Article]) -> int:
        new_count = 0
        now = datetime.now(timezone.utc)
        for article in articles:
            if article.content_hash not in self._seen:
                self._seen[article.content_hash] = now
                for symbol in article.related_symbols:
                    self._queue[symbol].append(article)
                new_count += 1
        return new_count

    def drain(self, symbol: str) -> list[Article]:
        return self._queue.pop(symbol, [])

    def symbols(self) -> list[str]:
        return [s for s, q in self._queue.items() if q]

    def pending_count(self, symbol: str) -> int:
        return len(self._queue.get(symbol, []))

    def expire(self) -> int:
        now = datetime.now(timezone.utc)
        expired = [h for h, ts in self._seen.items() if now - ts > self._max_age]
        for h in expired:
            del self._seen[h]
        return len(expired)
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/sentiment/test_article_buffer.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/sentiment/article_buffer.py tests/unit/sentiment/test_article_buffer.py
git commit -m "feat: add ArticleBuffer for deduplication and per-symbol queuing"
```

---

### Task 3: SentimentAggregator — Time-Weighted Rolling Scores

**Why:** Raw per-article scores need to be combined into a single rolling score per symbol, with recent articles weighted more heavily.

**Files:**
- Create: `src/sentiment/aggregator.py`
- Test: `tests/unit/sentiment/test_aggregator.py`

**Step 1: Write failing tests**

```python
# tests/unit/sentiment/test_aggregator.py
import pytest
from datetime import datetime, timedelta, timezone

from src.sentiment.models import SentimentResult


def _make_result(score=0.5, magnitude=0.8, hours_ago=0):
    ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return SentimentResult(score=score, magnitude=magnitude, timestamp=ts)


class TestSentimentAggregator:
    def test_no_scores_returns_zero(self):
        from src.sentiment.aggregator import SentimentAggregator
        agg = SentimentAggregator()
        assert agg.aggregate("AAPL", datetime.now(timezone.utc)) == 0.0

    def test_single_recent_score(self):
        from src.sentiment.aggregator import SentimentAggregator
        agg = SentimentAggregator()
        agg.add_scores("AAPL", [_make_result(score=0.8, magnitude=1.0, hours_ago=0)])
        result = agg.aggregate("AAPL", datetime.now(timezone.utc))
        assert abs(result - 0.8) < 0.01  # recent score, weight ~1.0

    def test_old_score_decays(self):
        from src.sentiment.aggregator import SentimentAggregator
        agg = SentimentAggregator(half_life_hours=6.0)
        # One score 12 hours ago = 2 half-lives, weight = 0.25
        agg.add_scores("AAPL", [_make_result(score=0.8, magnitude=1.0, hours_ago=12)])
        result = agg.aggregate("AAPL", datetime.now(timezone.utc))
        assert result < 0.5  # decayed significantly

    def test_recent_outweighs_old(self):
        from src.sentiment.aggregator import SentimentAggregator
        agg = SentimentAggregator(half_life_hours=6.0)
        agg.add_scores("AAPL", [
            _make_result(score=-0.8, magnitude=1.0, hours_ago=24),  # old negative
            _make_result(score=0.8, magnitude=1.0, hours_ago=0),    # recent positive
        ])
        result = agg.aggregate("AAPL", datetime.now(timezone.utc))
        assert result > 0  # recent positive dominates

    def test_magnitude_scales_contribution(self):
        from src.sentiment.aggregator import SentimentAggregator
        agg = SentimentAggregator()
        # High score but low magnitude vs low score high magnitude
        agg.add_scores("AAPL", [
            _make_result(score=0.9, magnitude=0.1, hours_ago=0),
            _make_result(score=0.3, magnitude=0.9, hours_ago=0),
        ])
        result = agg.aggregate("AAPL", datetime.now(timezone.utc))
        assert result < 0.5  # low-magnitude 0.9 doesn't dominate

    def test_prune_old_scores(self):
        from src.sentiment.aggregator import SentimentAggregator
        agg = SentimentAggregator(max_age_hours=1.0)
        agg.add_scores("AAPL", [_make_result(score=0.5, hours_ago=2)])
        pruned = agg.prune("AAPL", datetime.now(timezone.utc))
        assert pruned == 1
        assert agg.aggregate("AAPL", datetime.now(timezone.utc)) == 0.0

    def test_symbols_with_scores(self):
        from src.sentiment.aggregator import SentimentAggregator
        agg = SentimentAggregator()
        agg.add_scores("AAPL", [_make_result()])
        agg.add_scores("GOOG", [_make_result()])
        assert set(agg.symbols()) == {"AAPL", "GOOG"}

    def test_linear_decay(self):
        from src.sentiment.aggregator import SentimentAggregator
        agg = SentimentAggregator(decay="linear", half_life_hours=6.0)
        agg.add_scores("AAPL", [_make_result(score=0.8, magnitude=1.0, hours_ago=12)])
        result = agg.aggregate("AAPL", datetime.now(timezone.utc))
        assert result < 0.8  # decayed
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/sentiment/test_aggregator.py -v`
Expected: FAIL

**Step 3: Implement**

Create `src/sentiment/aggregator.py`:
```python
"""Time-weighted rolling sentiment scores per symbol."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from src.sentiment.models import SentimentResult


class SentimentAggregator:
    def __init__(
        self,
        decay: str = "exponential",
        half_life_hours: float = 6.0,
        max_age_hours: float = 48.0,
    ) -> None:
        self._scores: dict[str, list[SentimentResult]] = defaultdict(list)
        self._decay = decay
        self._half_life = timedelta(hours=half_life_hours)
        self._max_age = timedelta(hours=max_age_hours)

    def add_scores(self, symbol: str, scores: list[SentimentResult]) -> None:
        self._scores[symbol].extend(scores)

    def aggregate(self, symbol: str, now: datetime) -> float:
        scores = self._scores.get(symbol, [])
        if not scores:
            return 0.0

        weighted_sum = 0.0
        weight_total = 0.0

        for result in scores:
            age = now - result.timestamp
            if self._decay == "exponential":
                weight = 2 ** (-age / self._half_life)
            else:  # linear
                weight = max(0.0, 1.0 - age / (self._half_life * 4))

            weighted_sum += result.score * weight * result.magnitude
            weight_total += weight

        return weighted_sum / weight_total if weight_total > 0 else 0.0

    def prune(self, symbol: str, now: datetime) -> int:
        scores = self._scores.get(symbol, [])
        before = len(scores)
        self._scores[symbol] = [s for s in scores if now - s.timestamp <= self._max_age]
        return before - len(self._scores[symbol])

    def symbols(self) -> list[str]:
        return [s for s, scores in self._scores.items() if scores]
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/sentiment/test_aggregator.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/sentiment/aggregator.py tests/unit/sentiment/test_aggregator.py
git commit -m "feat: add SentimentAggregator with time-weighted decay scoring"
```

---

### Task 4: SentimentStore — DB Persistence

**Why:** Articles and sentiment scores need to be persisted for backtesting, analytics, and surviving restarts.

**Files:**
- Create: `src/sentiment/store.py`
- Test: `tests/unit/sentiment/test_store.py`

**Step 1: Write failing tests**

```python
# tests/unit/sentiment/test_store.py
import pytest
from datetime import datetime, timezone

from src.sentiment.models import Article, SentimentResult


def _make_article(**kwargs):
    defaults = dict(
        title="Test Article",
        body="Article body text",
        source="rss",
        url="https://example.com",
        published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        related_symbols=["AAPL"],
    )
    defaults.update(kwargs)
    return Article(**defaults)


def _make_result(article_id="abc", **kwargs):
    defaults = dict(
        score=0.7,
        magnitude=0.8,
        timestamp=datetime(2026, 1, 15, tzinfo=timezone.utc),
        article_id=article_id,
        analyzer="ollama",
    )
    defaults.update(kwargs)
    return SentimentResult(**defaults)


class TestSentimentStore:
    @pytest.fixture
    def store(self):
        from src.sentiment.store import SentimentStore
        return SentimentStore()

    def test_save_and_get_article(self, store):
        article = _make_article()
        store.save_articles([article])
        result = store.get_articles(symbol="AAPL")
        assert len(result) == 1
        assert result[0].title == "Test Article"

    def test_dedup_articles_by_content_hash(self, store):
        a = _make_article()
        store.save_articles([a, a])  # same hash
        assert len(store.get_articles(symbol="AAPL")) == 1

    def test_save_and_get_scores(self, store):
        article = _make_article()
        store.save_articles([article])
        result = _make_result(article_id=article.id)
        store.save_scores([result])
        scores = store.get_scores(symbol="AAPL")
        assert len(scores) == 1
        assert scores[0].score == 0.7

    def test_get_scores_by_analyzer(self, store):
        article = _make_article()
        store.save_articles([article])
        store.save_scores([
            _make_result(article_id=article.id, analyzer="ollama"),
            _make_result(article_id=article.id, analyzer="claude", score=0.9),
        ])
        scores = store.get_scores(symbol="AAPL", analyzer="claude")
        assert len(scores) == 1
        assert scores[0].analyzer == "claude"

    def test_get_articles_by_source(self, store):
        store.save_articles([
            _make_article(source="rss"),
            _make_article(source="reddit", title="Different"),
        ])
        rss = store.get_articles(symbol="AAPL", source="rss")
        assert len(rss) == 1
        assert rss[0].source == "rss"

    def test_article_count(self, store):
        store.save_articles([_make_article(), _make_article(title="B")])
        assert store.article_count() == 2
        assert store.article_count(symbol="AAPL") == 2
        assert store.article_count(symbol="GOOG") == 0

    def test_score_count(self, store):
        article = _make_article()
        store.save_articles([article])
        store.save_scores([_make_result(article_id=article.id)])
        assert store.score_count() == 1
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/sentiment/test_store.py -v`
Expected: FAIL

**Step 3: Implement**

Create `src/sentiment/store.py` — an in-memory store that mirrors the DB schema. This keeps Phase 2 self-contained; we'll wire it to SQLAlchemy in a later phase.

```python
"""In-memory sentiment store for articles and scores."""
from __future__ import annotations

from src.sentiment.models import Article, SentimentResult


class SentimentStore:
    def __init__(self) -> None:
        self._articles: dict[str, Article] = {}  # id -> Article
        self._article_hashes: set[str] = set()
        self._scores: list[SentimentResult] = []
        self._article_symbols: dict[str, list[str]] = {}  # article_id -> symbols

    def save_articles(self, articles: list[Article]) -> int:
        count = 0
        for article in articles:
            if article.content_hash not in self._article_hashes:
                self._articles[article.id] = article
                self._article_hashes.add(article.content_hash)
                self._article_symbols[article.id] = list(article.related_symbols)
                count += 1
        return count

    def get_articles(
        self,
        symbol: str | None = None,
        source: str | None = None,
        limit: int = 100,
    ) -> list[Article]:
        results = list(self._articles.values())
        if symbol is not None:
            results = [a for a in results if symbol in a.related_symbols]
        if source is not None:
            results = [a for a in results if a.source == source]
        return results[:limit]

    def save_scores(self, scores: list[SentimentResult]) -> int:
        self._scores.extend(scores)
        return len(scores)

    def get_scores(
        self,
        symbol: str | None = None,
        analyzer: str | None = None,
        limit: int = 100,
    ) -> list[SentimentResult]:
        results = list(self._scores)
        if analyzer is not None:
            results = [s for s in results if s.analyzer == analyzer]
        if symbol is not None:
            article_ids = {
                aid for aid, syms in self._article_symbols.items()
                if symbol in syms
            }
            results = [s for s in results if s.article_id in article_ids]
        return results[:limit]

    def article_count(self, symbol: str | None = None) -> int:
        if symbol is None:
            return len(self._articles)
        return len([a for a in self._articles.values() if symbol in a.related_symbols])

    def score_count(self, symbol: str | None = None) -> int:
        if symbol is None:
            return len(self._scores)
        return len(self.get_scores(symbol=symbol, limit=999999))
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/sentiment/test_store.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/sentiment/store.py tests/unit/sentiment/test_store.py
git commit -m "feat: add SentimentStore for article and score persistence"
```

---

### Task 5: SentimentPipeline — Orchestration

**Why:** The pipeline orchestrates the full flow: fetch articles from providers, buffer, score, aggregate, persist. This is the main entry point for the sentiment subsystem.

**Files:**
- Create: `src/sentiment/pipeline.py`
- Test: `tests/unit/sentiment/test_pipeline.py`

**Step 1: Write failing tests**

```python
# tests/unit/sentiment/test_pipeline.py
import pytest
from datetime import datetime, timezone

from src.sentiment.models import Article, SentimentResult
from src.providers.mock import MockNewsProvider, MockSentimentAnalyzer
from src.providers.configs import MockNewsConfig, MockSentimentConfig


def _canned_articles():
    return [
        {
            "title": "BTC surges past $100k",
            "body": "Bitcoin broke records today...",
            "source": "rss",
            "url": "https://example.com/1",
            "published_at": datetime(2026, 1, 15, tzinfo=timezone.utc).isoformat(),
            "related_symbols": ["BTC"],
        }
    ]


class TestSentimentPipeline:
    @pytest.fixture
    def pipeline(self):
        from src.sentiment.pipeline import SentimentPipeline
        news = MockNewsProvider(MockNewsConfig(canned_articles=_canned_articles()))
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.7))
        return SentimentPipeline(
            news_providers=[news],
            analyzer=analyzer,
        )

    @pytest.mark.asyncio
    async def test_fetch_populates_buffer(self, pipeline):
        count = await pipeline.fetch(symbols=["BTC"])
        assert count >= 1

    @pytest.mark.asyncio
    async def test_score_processes_buffered_articles(self, pipeline):
        await pipeline.fetch(symbols=["BTC"])
        scored = await pipeline.score(symbols=["BTC"])
        assert scored >= 1

    @pytest.mark.asyncio
    async def test_aggregate_returns_score(self, pipeline):
        await pipeline.fetch(symbols=["BTC"])
        await pipeline.score(symbols=["BTC"])
        result = pipeline.get_sentiment("BTC")
        assert result != 0.0  # should have a score now

    @pytest.mark.asyncio
    async def test_run_cycle_end_to_end(self, pipeline):
        result = await pipeline.run_cycle(symbols=["BTC"])
        assert "BTC" in result
        assert isinstance(result["BTC"], float)

    @pytest.mark.asyncio
    async def test_no_articles_returns_zero(self, pipeline):
        result = await pipeline.run_cycle(symbols=["UNKNOWN"])
        assert result.get("UNKNOWN", 0.0) == 0.0

    def test_store_has_articles_after_cycle(self, pipeline):
        import asyncio
        asyncio.get_event_loop().run_until_complete(pipeline.run_cycle(symbols=["BTC"]))
        assert pipeline.store.article_count() >= 1

    def test_store_has_scores_after_cycle(self, pipeline):
        import asyncio
        asyncio.get_event_loop().run_until_complete(pipeline.run_cycle(symbols=["BTC"]))
        assert pipeline.store.score_count() >= 1
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/sentiment/test_pipeline.py -v`
Expected: FAIL

**Step 3: Implement**

Create `src/sentiment/pipeline.py`:
```python
"""Orchestrates the sentiment analysis pipeline."""
from __future__ import annotations

from datetime import datetime, timezone

from src.sentiment.article_buffer import ArticleBuffer
from src.sentiment.aggregator import SentimentAggregator
from src.sentiment.models import Article, SentimentResult
from src.sentiment.store import SentimentStore


class SentimentPipeline:
    def __init__(
        self,
        news_providers: list,
        analyzer,
        buffer: ArticleBuffer | None = None,
        aggregator: SentimentAggregator | None = None,
        store: SentimentStore | None = None,
    ) -> None:
        self._news_providers = news_providers
        self._analyzer = analyzer
        self.buffer = buffer or ArticleBuffer()
        self.aggregator = aggregator or SentimentAggregator()
        self.store = store or SentimentStore()

    async def fetch(self, symbols: list[str]) -> int:
        total = 0
        for provider in self._news_providers:
            for symbol in symbols:
                raw_articles = await provider.fetch_articles(symbol)
                articles = [self._to_article(a, provider.name) for a in raw_articles]
                total += self.buffer.ingest(articles)
        return total

    async def score(self, symbols: list[str] | None = None) -> int:
        target_symbols = symbols or self.buffer.symbols()
        total = 0
        now = datetime.now(timezone.utc)

        for symbol in target_symbols:
            articles = self.buffer.drain(symbol)
            if not articles:
                continue

            self.store.save_articles(articles)
            texts = [f"{a.title}. {a.body}" for a in articles]
            results = await self._analyzer.score_batch(texts)

            scored_results = []
            for article, result in zip(articles, results):
                scored = SentimentResult(
                    score=result.score,
                    magnitude=result.magnitude,
                    timestamp=now,
                    reasoning=result.reasoning,
                    article_id=article.id,
                    analyzer=self._analyzer.name,
                )
                scored_results.append(scored)

            self.store.save_scores(scored_results)
            self.aggregator.add_scores(symbol, scored_results)
            total += len(scored_results)

        return total

    def get_sentiment(self, symbol: str) -> float:
        return self.aggregator.aggregate(symbol, datetime.now(timezone.utc))

    async def run_cycle(self, symbols: list[str]) -> dict[str, float]:
        await self.fetch(symbols)
        await self.score(symbols)
        return {s: self.get_sentiment(s) for s in symbols}

    @staticmethod
    def _to_article(raw: dict | Article, provider_name: str) -> Article:
        if isinstance(raw, Article):
            return raw
        return Article(
            title=raw.get("title", ""),
            body=raw.get("body", ""),
            source=raw.get("source", provider_name),
            url=raw.get("url", ""),
            published_at=raw.get("published_at", datetime.now(timezone.utc)),
            related_symbols=raw.get("related_symbols", []),
        )
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/sentiment/test_pipeline.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/sentiment/pipeline.py tests/unit/sentiment/test_pipeline.py
git commit -m "feat: add SentimentPipeline orchestrating fetch/score/aggregate cycle"
```

---

### Task 6: RSS News Provider — Real Implementation

**Why:** The first real news provider. Fetches articles from RSS feeds, extracts text, and maps to Article model. This validates the protocol works with a real implementation.

**Files:**
- Create: `src/providers/rss.py`
- Test: `tests/unit/providers/test_rss.py`
- Modify: `pyproject.toml` — add `feedparser` dependency

**Step 1: Add dependency**

```bash
# Add feedparser to pyproject.toml dependencies
```

Add `"feedparser>=6.0.0"` to the `[project] dependencies` list in `pyproject.toml`.

**Step 2: Write failing tests**

```python
# tests/unit/providers/test_rss.py
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from src.providers.configs import RSSConfig


class TestRSSNewsProvider:
    @pytest.fixture
    def config(self):
        return RSSConfig(feed_urls=["https://example.com/feed.xml"])

    def test_creates_with_config(self, config):
        from src.providers.rss import RSSNewsProvider
        provider = RSSNewsProvider(config)
        assert provider.name == "rss"

    def test_implements_protocol(self, config):
        from src.providers.rss import RSSNewsProvider
        from src.providers.protocols import NewsProvider
        provider = RSSNewsProvider(config)
        assert isinstance(provider, NewsProvider)

    def test_rate_limit_from_config(self, config):
        from src.providers.rss import RSSNewsProvider
        provider = RSSNewsProvider(config)
        assert provider.rate_limit == config.max_articles_per_fetch

    @pytest.mark.asyncio
    async def test_fetch_parses_feed_entries(self, config):
        from src.providers.rss import RSSNewsProvider

        mock_feed = {
            "entries": [
                {
                    "title": "BTC up 10%",
                    "summary": "Bitcoin rose sharply...",
                    "link": "https://example.com/1",
                    "published_parsed": (2026, 1, 15, 12, 0, 0, 0, 0, 0),
                },
            ],
            "bozo": False,
        }

        provider = RSSNewsProvider(config)
        with patch("src.providers.rss.feedparser.parse", return_value=mock_feed):
            articles = await provider.fetch_articles("BTC", limit=10)

        assert len(articles) == 1
        assert articles[0].title == "BTC up 10%"
        assert articles[0].source == "rss"
        assert "BTC" in articles[0].related_symbols

    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self, config):
        from src.providers.rss import RSSNewsProvider
        provider = RSSNewsProvider(config)
        # health_check should return True (feeds are always "available")
        assert await provider.health_check() is True
```

**Step 3: Implement**

Create `src/providers/rss.py`:
```python
"""RSS news provider implementation."""
from __future__ import annotations

import asyncio
from calendar import timegm
from datetime import datetime, timezone
from time import struct_time

import feedparser

from src.providers.configs import RSSConfig
from src.sentiment.models import Article


class RSSNewsProvider:
    def __init__(self, config: RSSConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "rss"

    @property
    def rate_limit(self) -> int:
        return self._config.max_articles_per_fetch

    async def fetch_articles(self, symbol: str, limit: int = 10) -> list[Article]:
        articles: list[Article] = []
        for url in self._config.feed_urls:
            feed = await asyncio.to_thread(feedparser.parse, url)
            for entry in feed.get("entries", [])[:limit]:
                published = self._parse_time(entry.get("published_parsed"))
                articles.append(
                    Article(
                        title=entry.get("title", ""),
                        body=entry.get("summary", ""),
                        source="rss",
                        url=entry.get("link", ""),
                        published_at=published,
                        related_symbols=[symbol],
                    )
                )
        return articles[:limit]

    async def health_check(self) -> bool:
        return True

    @staticmethod
    def _parse_time(t: struct_time | None) -> datetime:
        if t is None:
            return datetime.now(timezone.utc)
        return datetime.fromtimestamp(timegm(t), tz=timezone.utc)
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/providers/test_rss.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/providers/rss.py tests/unit/providers/test_rss.py pyproject.toml
git commit -m "feat: add RSS news provider with feedparser"
```

---

### Task 7: Ollama Sentiment Analyzer — Real Implementation

**Why:** First real sentiment analyzer. Uses Ollama (local, free) to score article sentiment. Validates the SentimentAnalyzer protocol with a real implementation.

**Files:**
- Create: `src/providers/ollama_sentiment.py`
- Test: `tests/unit/providers/test_ollama_sentiment.py`

**Step 1: Write failing tests**

```python
# tests/unit/providers/test_ollama_sentiment.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from src.providers.configs import OllamaSentimentConfig
from src.sentiment.models import SentimentResult


class TestOllamaSentimentAnalyzer:
    @pytest.fixture
    def config(self):
        return OllamaSentimentConfig()

    def test_creates_with_config(self, config):
        from src.providers.ollama_sentiment import OllamaSentimentAnalyzer
        analyzer = OllamaSentimentAnalyzer(config)
        assert analyzer.name == "ollama"

    def test_implements_protocol(self, config):
        from src.providers.ollama_sentiment import OllamaSentimentAnalyzer
        from src.providers.protocols import SentimentAnalyzer
        analyzer = OllamaSentimentAnalyzer(config)
        assert isinstance(analyzer, SentimentAnalyzer)

    @pytest.mark.asyncio
    async def test_score_returns_sentiment_result(self, config):
        from src.providers.ollama_sentiment import OllamaSentimentAnalyzer

        analyzer = OllamaSentimentAnalyzer(config)
        mock_response = {"message": {"content": '{"score": 0.7, "magnitude": 0.8, "reasoning": "positive"}'}}

        with patch.object(analyzer, "_call_ollama", new_callable=AsyncMock, return_value=mock_response):
            result = await analyzer.score("Bitcoin is surging")

        assert isinstance(result, SentimentResult)
        assert result.score == 0.7
        assert result.magnitude == 0.8

    @pytest.mark.asyncio
    async def test_score_batch_processes_all(self, config):
        from src.providers.ollama_sentiment import OllamaSentimentAnalyzer

        analyzer = OllamaSentimentAnalyzer(config)
        mock_response = {"message": {"content": '{"score": 0.5, "magnitude": 0.6, "reasoning": "ok"}'}}

        with patch.object(analyzer, "_call_ollama", new_callable=AsyncMock, return_value=mock_response):
            results = await analyzer.score_batch(["Text 1", "Text 2"])

        assert len(results) == 2
        assert all(isinstance(r, SentimentResult) for r in results)

    @pytest.mark.asyncio
    async def test_handles_malformed_response(self, config):
        from src.providers.ollama_sentiment import OllamaSentimentAnalyzer

        analyzer = OllamaSentimentAnalyzer(config)
        mock_response = {"message": {"content": "not valid json"}}

        with patch.object(analyzer, "_call_ollama", new_callable=AsyncMock, return_value=mock_response):
            result = await analyzer.score("Some text")

        # Should return a neutral fallback, not crash
        assert isinstance(result, SentimentResult)
        assert result.score == 0.0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/providers/test_ollama_sentiment.py -v`
Expected: FAIL

**Step 3: Implement**

Create `src/providers/ollama_sentiment.py`:
```python
"""Ollama-based sentiment analyzer."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from src.providers.configs import OllamaSentimentConfig
from src.sentiment.models import SentimentResult

PROMPT_TEMPLATE = """Analyze the sentiment of the following financial text.
Return ONLY a JSON object with these fields:
- "score": float from -1.0 (very negative) to 1.0 (very positive)
- "magnitude": float from 0.0 (uncertain) to 1.0 (very confident)
- "reasoning": brief explanation

Text: {text}

JSON:"""


class OllamaSentimentAnalyzer:
    def __init__(self, config: OllamaSentimentConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "ollama"

    async def score(self, text: str) -> SentimentResult:
        prompt = PROMPT_TEMPLATE.format(text=text[:500])
        try:
            response = await self._call_ollama(prompt)
            content = response["message"]["content"]
            data = json.loads(content)
            return SentimentResult(
                score=max(-1.0, min(1.0, float(data["score"]))),
                magnitude=max(0.0, min(1.0, float(data["magnitude"]))),
                timestamp=datetime.now(timezone.utc),
                reasoning=data.get("reasoning"),
                analyzer="ollama",
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return SentimentResult(
                score=0.0,
                magnitude=0.0,
                timestamp=datetime.now(timezone.utc),
                reasoning="Failed to parse Ollama response",
                analyzer="ollama",
            )

    async def score_batch(self, texts: list[str]) -> list[SentimentResult]:
        return [await self.score(text) for text in texts]

    async def _call_ollama(self, prompt: str) -> dict:
        async with httpx.AsyncClient(timeout=self._config.timeout) as client:
            resp = await client.post(
                f"{self._config.base_url}/api/chat",
                json={
                    "model": self._config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json",
                },
            )
            resp.raise_for_status()
            return resp.json()
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/providers/test_ollama_sentiment.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/providers/ollama_sentiment.py tests/unit/providers/test_ollama_sentiment.py
git commit -m "feat: add Ollama sentiment analyzer implementation"
```

---

### Task 8: Sentiment CLI Commands

**Why:** Expose the sentiment pipeline via CLI for manual inspection and debugging.

**Files:**
- Create: `src/cli/sentiment_cmd.py`
- Modify: `src/cli/main.py` — register sentiment subcommand
- Test: `tests/unit/cli/test_sentiment_cmd.py`

**Step 1: Write failing tests**

```python
# tests/unit/cli/test_sentiment_cmd.py
import pytest
from typer.testing import CliRunner

runner = CliRunner()


class TestSentimentStatus:
    def test_status_shows_summary(self):
        from src.cli.main import app
        result = runner.invoke(app, ["sentiment", "status"])
        assert result.exit_code == 0
        assert "Sentiment Pipeline" in result.stdout


class TestSentimentScores:
    def test_scores_shows_table(self):
        from src.cli.main import app
        result = runner.invoke(app, ["sentiment", "scores", "--symbol", "BTC"])
        assert result.exit_code == 0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/cli/test_sentiment_cmd.py -v`
Expected: FAIL

**Step 3: Implement**

Create `src/cli/sentiment_cmd.py`:
```python
"""Sentiment pipeline CLI commands."""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Sentiment pipeline commands.")
console = Console()


@app.command()
def status():
    """Show sentiment pipeline status summary."""
    console.print("[bold]Sentiment Pipeline Status[/bold]")
    console.print("  Providers: (none active)")
    console.print("  Articles: 0")
    console.print("  Scores: 0")
    console.print("  Use 'tradebot sentiment scores --symbol <SYM>' to see per-symbol scores.")


@app.command()
def scores(symbol: str = typer.Option(..., help="Symbol to show scores for")):
    """Show sentiment scores for a symbol."""
    table = Table(title=f"Sentiment Scores: {symbol}")
    table.add_column("Analyzer")
    table.add_column("Score")
    table.add_column("Magnitude")
    table.add_column("Time")
    console.print(table)
    console.print("No scores yet. Run a pipeline cycle first.")
```

Update `src/cli/main.py` to register the sentiment subcommand.

**Step 4: Run tests**

Run: `uv run pytest tests/unit/cli/test_sentiment_cmd.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/cli/sentiment_cmd.py src/cli/main.py tests/unit/cli/test_sentiment_cmd.py
git commit -m "feat: add tradebot sentiment CLI commands"
```

---

### Task 9: Integration — Wire Pipeline to SentimentStrategy

**Why:** The existing SentimentStrategy consumes ResearchReports. We need to bridge the pipeline's aggregated scores into ResearchReports so the strategy works with real sentiment data.

**Files:**
- Create: `src/sentiment/bridge.py`
- Test: `tests/unit/sentiment/test_bridge.py`

**Step 1: Write failing tests**

```python
# tests/unit/sentiment/test_bridge.py
import pytest
from datetime import datetime, timezone

from src.sentiment.models import SentimentResult
from src.sentiment.aggregator import SentimentAggregator
from src.core.models import ResearchReport


def _make_result(score=0.7, magnitude=0.8, hours_ago=0):
    from datetime import timedelta
    ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return SentimentResult(score=score, magnitude=magnitude, timestamp=ts)


class TestSentimentBridge:
    def test_to_research_reports_returns_reports(self):
        from src.sentiment.bridge import SentimentBridge
        agg = SentimentAggregator()
        agg.add_scores("AAPL", [_make_result(score=0.7)])
        bridge = SentimentBridge(aggregator=agg)

        reports = bridge.to_research_reports(["AAPL"])
        assert len(reports) == 1
        assert isinstance(reports[0], ResearchReport)
        assert reports[0].symbol == "AAPL"
        assert reports[0].sentiment_score == pytest.approx(0.7, abs=0.1)

    def test_skips_symbols_with_no_scores(self):
        from src.sentiment.bridge import SentimentBridge
        agg = SentimentAggregator()
        bridge = SentimentBridge(aggregator=agg)

        reports = bridge.to_research_reports(["AAPL"])
        assert len(reports) == 0

    def test_multiple_symbols(self):
        from src.sentiment.bridge import SentimentBridge
        agg = SentimentAggregator()
        agg.add_scores("AAPL", [_make_result(score=0.5)])
        agg.add_scores("GOOG", [_make_result(score=-0.3)])
        bridge = SentimentBridge(aggregator=agg)

        reports = bridge.to_research_reports(["AAPL", "GOOG"])
        assert len(reports) == 2
        symbols = {r.symbol for r in reports}
        assert symbols == {"AAPL", "GOOG"}
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/sentiment/test_bridge.py -v`
Expected: FAIL

**Step 3: Implement**

Create `src/sentiment/bridge.py`:
```python
"""Bridges sentiment pipeline output to ResearchReport format for strategies."""
from __future__ import annotations

from datetime import datetime, timezone

from src.core.models import ResearchReport
from src.sentiment.aggregator import SentimentAggregator


class SentimentBridge:
    def __init__(self, aggregator: SentimentAggregator) -> None:
        self._aggregator = aggregator

    def to_research_reports(self, symbols: list[str]) -> list[ResearchReport]:
        now = datetime.now(timezone.utc)
        reports: list[ResearchReport] = []

        for symbol in symbols:
            score = self._aggregator.aggregate(symbol, now)
            if score == 0.0 and symbol not in self._aggregator.symbols():
                continue

            reports.append(
                ResearchReport(
                    symbol=symbol,
                    summary=f"Aggregated sentiment score: {score:.3f}",
                    sentiment_score=max(-1.0, min(1.0, score)),
                    timestamp=now,
                    sources=["sentiment_pipeline"],
                )
            )

        return reports
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/sentiment/test_bridge.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/sentiment/bridge.py tests/unit/sentiment/test_bridge.py
git commit -m "feat: add SentimentBridge to convert pipeline output to ResearchReports"
```

---

### Task 10: End-to-End Integration Test

**Why:** Verify the full pipeline works: mock news → buffer → score → aggregate → bridge → strategy signal.

**Files:**
- Create: `tests/integration/test_sentiment_e2e.py`

**Step 1: Write the integration test**

```python
# tests/integration/__init__.py  (empty)
# tests/integration/test_sentiment_e2e.py
import pytest
from datetime import datetime, timezone

from src.providers.mock import MockNewsProvider, MockSentimentAnalyzer
from src.providers.configs import MockNewsConfig, MockSentimentConfig
from src.sentiment.pipeline import SentimentPipeline
from src.sentiment.bridge import SentimentBridge
from src.agents.strategies.sentiment import SentimentStrategy


class TestSentimentE2E:
    @pytest.fixture
    def pipeline(self):
        canned = [
            {
                "title": "Bitcoin surges past $100k",
                "body": "BTC hit new all-time high today as institutional demand grows.",
                "source": "rss",
                "url": "https://example.com/1",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "related_symbols": ["BTC"],
            },
            {
                "title": "Crypto market bullish",
                "body": "Analysts predict continued growth in crypto markets.",
                "source": "rss",
                "url": "https://example.com/2",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "related_symbols": ["BTC"],
            },
        ]
        news = MockNewsProvider(MockNewsConfig(canned_articles=canned))
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=0.8, default_magnitude=0.9))
        return SentimentPipeline(news_providers=[news], analyzer=analyzer)

    @pytest.mark.asyncio
    async def test_pipeline_to_strategy_signal(self, pipeline):
        """Full flow: fetch → score → aggregate → bridge → strategy → BUY signal."""
        from src.core.models import MarketTick, AssetType
        from decimal import Decimal

        # Run pipeline cycle
        scores = await pipeline.run_cycle(symbols=["BTC"])
        assert scores["BTC"] > 0.5

        # Bridge to research reports
        bridge = SentimentBridge(aggregator=pipeline.aggregator)
        reports = bridge.to_research_reports(["BTC"])
        assert len(reports) == 1
        assert reports[0].sentiment_score > 0.5

        # Feed to strategy
        strategy = SentimentStrategy(buy_threshold=0.6, sell_threshold=-0.6)
        tick = MarketTick(
            symbol="BTC",
            price=Decimal("100000"),
            volume=1000,
            timestamp=datetime.now(timezone.utc),
            asset_type=AssetType.CRYPTO,
        )
        signal = await strategy.evaluate("BTC", [tick], research=reports)
        assert signal is not None
        assert signal.direction.value == "buy"

    @pytest.mark.asyncio
    async def test_negative_sentiment_generates_sell(self):
        """Negative sentiment → SELL signal."""
        from src.core.models import MarketTick, AssetType
        from decimal import Decimal

        canned = [{
            "title": "Crypto crash",
            "body": "Markets plummet as regulation fears grow.",
            "source": "rss",
            "url": "https://example.com/crash",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "related_symbols": ["BTC"],
        }]
        news = MockNewsProvider(MockNewsConfig(canned_articles=canned))
        analyzer = MockSentimentAnalyzer(MockSentimentConfig(default_score=-0.8, default_magnitude=0.9))
        pipeline = SentimentPipeline(news_providers=[news], analyzer=analyzer)

        await pipeline.run_cycle(symbols=["BTC"])
        bridge = SentimentBridge(aggregator=pipeline.aggregator)
        reports = bridge.to_research_reports(["BTC"])

        strategy = SentimentStrategy(buy_threshold=0.6, sell_threshold=-0.6)
        tick = MarketTick(
            symbol="BTC",
            price=Decimal("100000"),
            volume=1000,
            timestamp=datetime.now(timezone.utc),
            asset_type=AssetType.CRYPTO,
        )
        signal = await strategy.evaluate("BTC", [tick], research=reports)
        assert signal is not None
        assert signal.direction.value == "sell"
```

**Step 2: Run integration test**

Run: `uv run pytest tests/integration/test_sentiment_e2e.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/integration/
git commit -m "test: add end-to-end integration test for sentiment pipeline"
```

---

### Task 11: Full Regression Check + Cleanup

**Why:** Final verification that all existing tests still pass and nothing is broken.

**Files:** None new — just run everything.

**Step 1: Run full test suite**

```bash
uv run pytest tests/ -v --ignore=tests/test_db.py --ignore=tests/test_db_loader.py
```

Expected: ALL PASS (296+ pre-existing + ~50 new = 346+ total)

**Step 2: Fix any regressions**

If any tests fail, fix them.

**Step 3: Commit any fixes**

```bash
git add -A && git commit -m "fix: resolve regressions from Phase 2 integration"
```

(Only if needed.)
