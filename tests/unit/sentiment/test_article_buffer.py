"""Tests for ArticleBuffer deduplication and per-symbol queuing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.sentiment.article_buffer import ArticleBuffer
from src.sentiment.models import Article


def _make_article(
    title: str = "Test article",
    body: str = "body",
    source: str = "test",
    symbols: list[str] | None = None,
) -> Article:
    """Helper to build an Article with sensible defaults."""
    return Article(
        title=title,
        body=body,
        source=source,
        published_at=datetime.now(UTC),
        related_symbols=symbols or ["BTC"],
    )


class TestArticleBuffer:
    """Tests for the ArticleBuffer class."""

    # -- ingest ---------------------------------------------------------------

    def test_ingest_new_articles_returns_count(self):
        buf = ArticleBuffer()
        articles = [_make_article(title=f"Article {i}") for i in range(3)]
        assert buf.ingest(articles) == 3

    def test_ingest_empty_list_returns_zero(self):
        buf = ArticleBuffer()
        assert buf.ingest([]) == 0

    # -- dedup ----------------------------------------------------------------

    def test_dedup_same_hash_second_ingest_returns_zero(self):
        buf = ArticleBuffer()
        a = _make_article(title="Dup article", body="same body")
        b = _make_article(title="Dup article", body="same body")
        assert a.content_hash == b.content_hash  # sanity check

        assert buf.ingest([a]) == 1
        assert buf.ingest([b]) == 0

    def test_dedup_within_single_batch(self):
        """If two articles in the same batch share a hash, only one is ingested."""
        buf = ArticleBuffer()
        a = _make_article(title="Same", body="same")
        b = _make_article(title="Same", body="same")
        assert buf.ingest([a, b]) == 1

    # -- drain ----------------------------------------------------------------

    def test_drain_returns_articles_and_clears_queue(self):
        buf = ArticleBuffer()
        articles = [_make_article(title=f"A{i}", symbols=["ETH"]) for i in range(2)]
        buf.ingest(articles)

        drained = buf.drain("ETH")
        assert len(drained) == 2
        assert all(isinstance(a, Article) for a in drained)

        # queue should be empty now
        assert buf.drain("ETH") == []

    def test_drain_unknown_symbol_returns_empty(self):
        buf = ArticleBuffer()
        assert buf.drain("DOGE") == []

    # -- multi-symbol ---------------------------------------------------------

    def test_multi_symbol_article_queued_to_each(self):
        buf = ArticleBuffer()
        a = _make_article(title="BTC and ETH news", symbols=["BTC", "ETH"])
        buf.ingest([a])

        btc_articles = buf.drain("BTC")
        eth_articles = buf.drain("ETH")
        assert len(btc_articles) == 1
        assert len(eth_articles) == 1
        assert btc_articles[0].id == eth_articles[0].id

    # -- expire ---------------------------------------------------------------

    def test_expire_old_hashes_allows_reingest(self):
        buf = ArticleBuffer(max_age=timedelta(seconds=0))
        a = _make_article(title="Expire me")
        assert buf.ingest([a]) == 1

        # drain so the queue is empty
        buf.drain("BTC")

        # expire immediately (max_age=0s means everything is already old)
        removed = buf.expire()
        assert removed >= 1

        # same article can now be re-ingested
        b = _make_article(title="Expire me")
        assert a.content_hash == b.content_hash
        assert buf.ingest([b]) == 1

    def test_expire_keeps_recent_hashes(self):
        buf = ArticleBuffer(max_age=timedelta(hours=24))
        a = _make_article(title="Keep me")
        buf.ingest([a])

        removed = buf.expire()
        assert removed == 0

        # still deduped because hash was not expired
        b = _make_article(title="Keep me")
        assert buf.ingest([b]) == 0

    # -- symbols --------------------------------------------------------------

    def test_symbols_returns_symbols_with_pending(self):
        buf = ArticleBuffer()
        buf.ingest([_make_article(symbols=["BTC"])])
        buf.ingest([_make_article(title="Other", symbols=["ETH"])])

        syms = buf.symbols()
        assert sorted(syms) == ["BTC", "ETH"]

    def test_symbols_excludes_drained(self):
        buf = ArticleBuffer()
        buf.ingest([_make_article(symbols=["BTC"])])
        buf.drain("BTC")

        assert "BTC" not in buf.symbols()

    # -- pending_count --------------------------------------------------------

    def test_pending_count_returns_correct_count(self):
        buf = ArticleBuffer()
        buf.ingest([_make_article(title=f"A{i}", symbols=["SOL"]) for i in range(5)])
        assert buf.pending_count("SOL") == 5

    def test_pending_count_zero_for_unknown_symbol(self):
        buf = ArticleBuffer()
        assert buf.pending_count("XRP") == 0

    def test_pending_count_decreases_after_drain(self):
        buf = ArticleBuffer()
        buf.ingest([_make_article(symbols=["BTC"])])
        assert buf.pending_count("BTC") == 1
        buf.drain("BTC")
        assert buf.pending_count("BTC") == 0
