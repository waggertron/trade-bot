"""Tests for feed seed script that parses the reference doc."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.db.database import Database
from src.db.seed_feeds import parse_feeds_from_reference, seed_feeds_from_reference

REFERENCE_DOC = Path("docs/reference/free-news-feeds-reference.md")


class TestParseFeedsFromReference:
    def test_parses_at_least_100_feeds(self):
        records = parse_feeds_from_reference(REFERENCE_DOC)
        assert len(records) >= 100

    def test_all_records_have_required_fields(self):
        records = parse_feeds_from_reference(REFERENCE_DOC)
        for r in records:
            assert r.name, f"Missing name: {r}"
            assert r.url, f"Missing URL: {r}"
            assert r.feed_type in ("rss", "json_api", "government"), f"Bad feed_type: {r.feed_type}"
            assert r.category, f"Missing category: {r}"
            assert r.auth_type in ("free", "api_key"), f"Bad auth_type: {r.auth_type}"

    def test_categories_include_expected(self):
        records = parse_feeds_from_reference(REFERENCE_DOC)
        categories = {r.category for r in records}
        assert "markets" in categories
        assert "politics" in categories
        assert "technology" in categories

    def test_feed_types_include_all_three(self):
        records = parse_feeds_from_reference(REFERENCE_DOC)
        types = {r.feed_type for r in records}
        assert "rss" in types
        assert "json_api" in types
        assert "government" in types

    def test_api_key_feeds_detected(self):
        records = parse_feeds_from_reference(REFERENCE_DOC)
        api_key_feeds = [r for r in records if r.auth_type == "api_key"]
        assert len(api_key_feeds) >= 5  # Finnhub, Alpha Vantage, Polygon, etc.

    def test_known_feed_present(self):
        """CNBC Top News should be in the parsed output."""
        records = parse_feeds_from_reference(REFERENCE_DOC)
        names = {r.name for r in records}
        assert "CNBC Top News" in names

    def test_no_duplicate_urls(self):
        records = parse_feeds_from_reference(REFERENCE_DOC)
        urls = [r.url for r in records]
        assert len(urls) == len(set(urls)), "Duplicate URLs found"

    def test_rate_limits_parsed_for_known_providers(self):
        records = parse_feeds_from_reference(REFERENCE_DOC)
        by_name = {r.name: r for r in records}
        finnhub = by_name.get("Finnhub")
        if finnhub:
            assert finnhub.rate_limit_rpm == 60


class TestSeedFeedsFromReference:
    @pytest.mark.asyncio
    async def test_seeds_into_database(self, tmp_path):
        url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
        db = Database(url)
        await db.initialize()
        try:
            count = await seed_feeds_from_reference(db)
            assert count >= 100
            feeds = await db.list_feeds()
            assert len(feeds) >= 100
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_seed_is_idempotent(self, tmp_path):
        url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
        db = Database(url)
        await db.initialize()
        try:
            count1 = await seed_feeds_from_reference(db)
            await seed_feeds_from_reference(db)
            feeds = await db.list_feeds()
            assert len(feeds) == count1  # No duplicates added
        finally:
            await db.close()
