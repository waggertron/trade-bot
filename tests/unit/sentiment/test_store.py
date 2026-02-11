"""Tests for SentimentStore — in-memory persistence for articles and scores."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.sentiment.models import Article, SentimentResult
from src.sentiment.store import SentimentStore


# -- Helpers ------------------------------------------------------------------


def _make_article(
    title: str = "Bitcoin hits $100k",
    body: str = "Full body text",
    source: str = "reuters",
    symbols: list[str] | None = None,
    url: str = "",
) -> Article:
    return Article(
        title=title,
        body=body,
        source=source,
        url=url,
        published_at=datetime.now(timezone.utc),
        related_symbols=symbols or ["BTC"],
    )


def _make_score(
    article_id: str | None = None,
    score: float = 0.5,
    magnitude: float = 0.8,
    analyzer: str | None = "ollama-llama3",
) -> SentimentResult:
    return SentimentResult(
        score=score,
        magnitude=magnitude,
        timestamp=datetime.now(timezone.utc),
        article_id=article_id,
        analyzer=analyzer,
    )


# -- Save & Get Articles -----------------------------------------------------


class TestSaveAndGetArticles:
    def test_save_returns_count(self):
        store = SentimentStore()
        articles = [_make_article(), _make_article(title="ETH surges")]
        saved = store.save_articles(articles)
        assert saved == 2

    def test_get_articles_returns_saved(self):
        store = SentimentStore()
        article = _make_article()
        store.save_articles([article])
        result = store.get_articles()
        assert len(result) == 1
        assert result[0].id == article.id

    def test_get_articles_default_limit(self):
        store = SentimentStore()
        articles = [_make_article(title=f"Article {i}") for i in range(150)]
        store.save_articles(articles)
        result = store.get_articles()
        assert len(result) == 100  # default limit

    def test_get_articles_custom_limit(self):
        store = SentimentStore()
        articles = [_make_article(title=f"Article {i}") for i in range(10)]
        store.save_articles(articles)
        result = store.get_articles(limit=5)
        assert len(result) == 5

    def test_save_empty_list(self):
        store = SentimentStore()
        saved = store.save_articles([])
        assert saved == 0
        assert store.get_articles() == []


# -- Dedup Articles -----------------------------------------------------------


class TestDedupArticles:
    def test_dedup_by_content_hash(self):
        store = SentimentStore()
        a1 = _make_article(title="Same title", body="Same body")
        a2 = _make_article(title="Same title", body="Same body")
        assert a1.content_hash == a2.content_hash  # sanity check

        saved = store.save_articles([a1])
        assert saved == 1
        saved2 = store.save_articles([a2])
        assert saved2 == 0  # duplicate, not saved
        assert len(store.get_articles()) == 1

    def test_dedup_within_single_batch(self):
        store = SentimentStore()
        a1 = _make_article(title="Same title", body="Same body")
        a2 = _make_article(title="Same title", body="Same body")
        saved = store.save_articles([a1, a2])
        assert saved == 1
        assert len(store.get_articles()) == 1

    def test_different_content_not_deduped(self):
        store = SentimentStore()
        a1 = _make_article(title="Title A", body="Body A")
        a2 = _make_article(title="Title B", body="Body B")
        saved = store.save_articles([a1, a2])
        assert saved == 2
        assert len(store.get_articles()) == 2


# -- Filter Articles by Source ------------------------------------------------


class TestFilterArticlesBySource:
    def test_filter_by_source(self):
        store = SentimentStore()
        a1 = _make_article(source="reuters")
        a2 = _make_article(title="Other article", source="bloomberg")
        store.save_articles([a1, a2])

        result = store.get_articles(source="reuters")
        assert len(result) == 1
        assert result[0].source == "reuters"

    def test_filter_by_source_no_match(self):
        store = SentimentStore()
        store.save_articles([_make_article(source="reuters")])
        result = store.get_articles(source="bloomberg")
        assert len(result) == 0


# -- Filter Articles by Symbol ------------------------------------------------


class TestFilterArticlesBySymbol:
    def test_filter_by_symbol(self):
        store = SentimentStore()
        a1 = _make_article(symbols=["BTC"])
        a2 = _make_article(title="ETH article", symbols=["ETH"])
        store.save_articles([a1, a2])

        result = store.get_articles(symbol="BTC")
        assert len(result) == 1
        assert "BTC" in result[0].related_symbols

    def test_filter_by_symbol_multi_symbol_article(self):
        store = SentimentStore()
        a1 = _make_article(symbols=["BTC", "ETH"])
        store.save_articles([a1])

        btc = store.get_articles(symbol="BTC")
        eth = store.get_articles(symbol="ETH")
        assert len(btc) == 1
        assert len(eth) == 1

    def test_filter_by_symbol_and_source(self):
        store = SentimentStore()
        a1 = _make_article(symbols=["BTC"], source="reuters")
        a2 = _make_article(title="Other", symbols=["BTC"], source="bloomberg")
        a3 = _make_article(title="ETH news", symbols=["ETH"], source="reuters")
        store.save_articles([a1, a2, a3])

        result = store.get_articles(symbol="BTC", source="reuters")
        assert len(result) == 1
        assert result[0].id == a1.id


# -- Save & Get Scores -------------------------------------------------------


class TestSaveAndGetScores:
    def test_save_returns_count(self):
        store = SentimentStore()
        scores = [_make_score(), _make_score(score=-0.3)]
        saved = store.save_scores(scores)
        assert saved == 2

    def test_get_scores_returns_saved(self):
        store = SentimentStore()
        s = _make_score()
        store.save_scores([s])
        result = store.get_scores()
        assert len(result) == 1
        assert result[0].score == s.score

    def test_get_scores_default_limit(self):
        store = SentimentStore()
        scores = [_make_score(score=i / 200) for i in range(150)]
        store.save_scores(scores)
        result = store.get_scores()
        assert len(result) == 100

    def test_get_scores_custom_limit(self):
        store = SentimentStore()
        scores = [_make_score(score=i / 20) for i in range(10)]
        store.save_scores(scores)
        result = store.get_scores(limit=3)
        assert len(result) == 3

    def test_save_empty_list(self):
        store = SentimentStore()
        saved = store.save_scores([])
        assert saved == 0
        assert store.get_scores() == []


# -- Filter Scores by Analyzer -----------------------------------------------


class TestFilterScoresByAnalyzer:
    def test_filter_by_analyzer(self):
        store = SentimentStore()
        s1 = _make_score(analyzer="ollama-llama3")
        s2 = _make_score(analyzer="openai-gpt4")
        store.save_scores([s1, s2])

        result = store.get_scores(analyzer="ollama-llama3")
        assert len(result) == 1
        assert result[0].analyzer == "ollama-llama3"

    def test_filter_by_analyzer_no_match(self):
        store = SentimentStore()
        store.save_scores([_make_score(analyzer="ollama-llama3")])
        result = store.get_scores(analyzer="nonexistent")
        assert len(result) == 0


# -- Filter Scores by Symbol -------------------------------------------------


class TestFilterScoresBySymbol:
    def test_filter_by_symbol_via_article(self):
        store = SentimentStore()
        article = _make_article(symbols=["BTC"])
        store.save_articles([article])

        s = _make_score(article_id=article.id)
        store.save_scores([s])

        result = store.get_scores(symbol="BTC")
        assert len(result) == 1

    def test_filter_by_symbol_excludes_other_symbols(self):
        store = SentimentStore()
        btc_article = _make_article(symbols=["BTC"])
        eth_article = _make_article(title="ETH news", symbols=["ETH"])
        store.save_articles([btc_article, eth_article])

        s1 = _make_score(article_id=btc_article.id)
        s2 = _make_score(article_id=eth_article.id)
        store.save_scores([s1, s2])

        result = store.get_scores(symbol="BTC")
        assert len(result) == 1
        assert result[0].article_id == btc_article.id

    def test_filter_by_symbol_and_analyzer(self):
        store = SentimentStore()
        article = _make_article(symbols=["BTC"])
        store.save_articles([article])

        s1 = _make_score(article_id=article.id, analyzer="ollama-llama3")
        s2 = _make_score(article_id=article.id, analyzer="openai-gpt4")
        store.save_scores([s1, s2])

        result = store.get_scores(symbol="BTC", analyzer="ollama-llama3")
        assert len(result) == 1
        assert result[0].analyzer == "ollama-llama3"

    def test_scores_without_article_id_not_returned_for_symbol_filter(self):
        store = SentimentStore()
        s = _make_score(article_id=None)
        store.save_scores([s])

        result = store.get_scores(symbol="BTC")
        assert len(result) == 0


# -- Counts -------------------------------------------------------------------


class TestCounts:
    def test_article_count(self):
        store = SentimentStore()
        store.save_articles([_make_article(), _make_article(title="Other")])
        assert store.article_count() == 2

    def test_article_count_by_symbol(self):
        store = SentimentStore()
        store.save_articles([
            _make_article(symbols=["BTC"]),
            _make_article(title="ETH article", symbols=["ETH"]),
            _make_article(title="Both", symbols=["BTC", "ETH"]),
        ])
        assert store.article_count(symbol="BTC") == 2
        assert store.article_count(symbol="ETH") == 2

    def test_score_count(self):
        store = SentimentStore()
        store.save_scores([_make_score(), _make_score(score=-0.1)])
        assert store.score_count() == 2

    def test_score_count_by_symbol(self):
        store = SentimentStore()
        btc_art = _make_article(symbols=["BTC"])
        eth_art = _make_article(title="ETH news", symbols=["ETH"])
        store.save_articles([btc_art, eth_art])

        store.save_scores([
            _make_score(article_id=btc_art.id),
            _make_score(article_id=eth_art.id),
            _make_score(article_id=btc_art.id, score=-0.2),
        ])
        assert store.score_count(symbol="BTC") == 2
        assert store.score_count(symbol="ETH") == 1

    def test_counts_empty_store(self):
        store = SentimentStore()
        assert store.article_count() == 0
        assert store.score_count() == 0
