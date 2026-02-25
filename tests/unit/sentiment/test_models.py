"""Tests for shared sentiment models: Article and SentimentResult."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.sentiment.models import Article, SentimentResult

# -- Article ------------------------------------------------------------------


class TestArticle:
    """Tests for the Article Pydantic model."""

    def test_creation_with_required_fields(self):
        now = datetime.now(UTC)
        article = Article(
            title="Bitcoin hits $100k",
            source="reuters",
            published_at=now,
            related_symbols=["BTC"],
        )
        assert article.title == "Bitcoin hits $100k"
        assert article.source == "reuters"
        assert article.published_at == now
        assert article.related_symbols == ["BTC"]
        assert article.body == ""
        assert article.url == ""

    def test_auto_generated_id(self):
        article = Article(
            title="Test",
            source="test",
            published_at=datetime.now(UTC),
            related_symbols=[],
        )
        assert article.id is not None
        assert len(article.id) == 32  # uuid4 hex is 32 chars

    def test_unique_ids(self):
        a1 = Article(
            title="Test",
            source="test",
            published_at=datetime.now(UTC),
            related_symbols=[],
        )
        a2 = Article(
            title="Test",
            source="test",
            published_at=datetime.now(UTC),
            related_symbols=[],
        )
        assert a1.id != a2.id

    def test_auto_content_hash(self):
        article = Article(
            title="Bitcoin hits $100k",
            body="Full body text here",
            source="reuters",
            published_at=datetime.now(UTC),
            related_symbols=["BTC"],
        )
        assert article.content_hash is not None
        assert len(article.content_hash) == 64  # sha256 hex is 64 chars

    def test_same_content_same_hash(self):
        kwargs = dict(
            title="Bitcoin hits $100k",
            body="Full body text here",
            source="reuters",
            published_at=datetime.now(UTC),
            related_symbols=["BTC"],
        )
        a1 = Article(**kwargs)
        a2 = Article(**kwargs)
        assert a1.content_hash == a2.content_hash

    def test_different_content_different_hash(self):
        common = dict(
            source="reuters",
            published_at=datetime.now(UTC),
            related_symbols=["BTC"],
        )
        a1 = Article(title="Bitcoin hits $100k", body="body A", **common)
        a2 = Article(title="Bitcoin crashes to $50k", body="body B", **common)
        assert a1.content_hash != a2.content_hash

    def test_content_hash_uses_body_prefix(self):
        """content_hash should use only body[:200], so bodies differing only
        after the 200th character should produce the same hash."""
        common = dict(
            title="Same title",
            source="test",
            published_at=datetime.now(UTC),
            related_symbols=[],
        )
        shared_prefix = "A" * 200
        a1 = Article(body=shared_prefix + "XXXX", **common)
        a2 = Article(body=shared_prefix + "YYYY", **common)
        assert a1.content_hash == a2.content_hash

    def test_frozen(self):
        article = Article(
            title="Test",
            source="test",
            published_at=datetime.now(UTC),
            related_symbols=[],
        )
        with pytest.raises(ValidationError):
            article.title = "Changed"  # type: ignore[misc]

    def test_auto_fetched_at(self):
        before = datetime.now(UTC)
        article = Article(
            title="Test",
            source="test",
            published_at=datetime.now(UTC),
            related_symbols=[],
        )
        after = datetime.now(UTC)
        assert before <= article.fetched_at <= after

    def test_serialization_roundtrip(self):
        now = datetime.now(UTC)
        article = Article(
            title="Bitcoin hits $100k",
            body="Some body",
            source="reuters",
            url="https://example.com/article",
            published_at=now,
            related_symbols=["BTC", "ETH"],
        )
        data = article.model_dump()
        restored = Article.model_validate(data)
        assert restored.title == article.title
        assert restored.body == article.body
        assert restored.source == article.source
        assert restored.url == article.url
        assert restored.id == article.id
        assert restored.content_hash == article.content_hash
        assert restored.related_symbols == article.related_symbols


# -- SentimentResult ----------------------------------------------------------


class TestSentimentResult:
    """Tests for the SentimentResult Pydantic model."""

    def test_creates_valid(self):
        result = SentimentResult(
            score=0.5,
            magnitude=0.8,
            timestamp=datetime.now(UTC),
            reasoning="positive outlook",
        )
        assert result.score == 0.5
        assert result.magnitude == 0.8
        assert result.reasoning == "positive outlook"

    def test_optional_fields_default_to_none(self):
        result = SentimentResult(
            score=0.0,
            magnitude=0.5,
            timestamp=datetime.now(UTC),
        )
        assert result.reasoning is None
        assert result.article_id is None
        assert result.analyzer is None

    def test_article_id_and_analyzer(self):
        result = SentimentResult(
            score=0.5,
            magnitude=0.8,
            timestamp=datetime.now(UTC),
            article_id="abc123",
            analyzer="ollama-llama3",
        )
        assert result.article_id == "abc123"
        assert result.analyzer == "ollama-llama3"

    def test_frozen(self):
        result = SentimentResult(
            score=0.5,
            magnitude=0.8,
            timestamp=datetime.now(UTC),
        )
        with pytest.raises(ValidationError):
            result.score = 0.9  # type: ignore[misc]

    def test_rejects_score_above_1(self):
        with pytest.raises(ValidationError):
            SentimentResult(
                score=1.5,
                magnitude=0.5,
                timestamp=datetime.now(UTC),
            )

    def test_rejects_score_below_neg1(self):
        with pytest.raises(ValidationError):
            SentimentResult(
                score=-1.5,
                magnitude=0.5,
                timestamp=datetime.now(UTC),
            )

    def test_rejects_magnitude_above_1(self):
        with pytest.raises(ValidationError):
            SentimentResult(
                score=0.5,
                magnitude=1.5,
                timestamp=datetime.now(UTC),
            )

    def test_rejects_magnitude_below_0(self):
        with pytest.raises(ValidationError):
            SentimentResult(
                score=0.5,
                magnitude=-0.1,
                timestamp=datetime.now(UTC),
            )

    def test_boundary_values_accepted(self):
        """Score at -1 and 1, magnitude at 0 and 1 should be valid."""
        r1 = SentimentResult(score=-1.0, magnitude=0.0, timestamp=datetime.now(UTC))
        assert r1.score == -1.0
        assert r1.magnitude == 0.0

        r2 = SentimentResult(score=1.0, magnitude=1.0, timestamp=datetime.now(UTC))
        assert r2.score == 1.0
        assert r2.magnitude == 1.0

    def test_importable_from_new_location(self):
        """Verify we can import SentimentResult from src.sentiment.models."""
        from src.sentiment.models import SentimentResult as SR

        assert SR is SentimentResult

    def test_serialization_roundtrip(self):
        now = datetime.now(UTC)
        result = SentimentResult(
            score=0.75,
            magnitude=0.6,
            timestamp=now,
            reasoning="bullish momentum",
            article_id="test-id",
            analyzer="test-analyzer",
        )
        data = result.model_dump()
        restored = SentimentResult.model_validate(data)
        assert restored.score == result.score
        assert restored.magnitude == result.magnitude
        assert restored.reasoning == result.reasoning
        assert restored.article_id == result.article_id
        assert restored.analyzer == result.analyzer
