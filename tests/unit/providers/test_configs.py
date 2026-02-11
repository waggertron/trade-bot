"""Tests for provider config models."""

from __future__ import annotations

import json

import pytest

from src.providers.configs import (
    KrakenMarketConfig,
    MockMarketConfig,
    MockSentimentConfig,
    OllamaSentimentConfig,
    RateLimit,
    RSSConfig,
)


class TestRateLimit:
    def test_creates_with_valid_value(self):
        rl = RateLimit(requests_per_minute=60)
        assert rl.requests_per_minute == 60

    def test_rejects_zero(self):
        with pytest.raises(Exception):
            RateLimit(requests_per_minute=0)

    def test_rejects_negative(self):
        with pytest.raises(Exception):
            RateLimit(requests_per_minute=-1)


class TestKrakenMarketConfig:
    def test_defaults(self):
        cfg = KrakenMarketConfig()
        assert cfg.base_url == "https://api.kraken.com"
        assert cfg.api_key == ""
        assert cfg.api_secret == ""
        assert cfg.timeout == 10.0

    def test_custom_values(self):
        cfg = KrakenMarketConfig(
            base_url="https://custom.kraken.com",
            api_key="key123",
            api_secret="secret456",
            timeout=5.0,
        )
        assert cfg.base_url == "https://custom.kraken.com"
        assert cfg.api_key == "key123"
        assert cfg.api_secret == "secret456"
        assert cfg.timeout == 5.0


class TestMockMarketConfig:
    def test_defaults(self):
        cfg = MockMarketConfig()
        assert cfg.should_fail is False
        assert cfg.default_prices == {}
        assert cfg.latency_ms == 0
        assert cfg.timeout == 10.0

    def test_custom_prices(self):
        cfg = MockMarketConfig(default_prices={"BTC": "50000.00"})
        assert cfg.default_prices == {"BTC": "50000.00"}


class TestRSSConfig:
    def test_requires_non_empty_feed_urls(self):
        with pytest.raises(Exception):
            RSSConfig(feed_urls=[])

    def test_valid_feed_urls(self):
        cfg = RSSConfig(feed_urls=["https://example.com/rss"])
        assert cfg.feed_urls == ["https://example.com/rss"]


class TestOllamaSentimentConfig:
    def test_defaults(self):
        cfg = OllamaSentimentConfig()
        assert cfg.model == "llama3.2"
        assert cfg.base_url == "http://localhost:11434"
        assert cfg.timeout == 30.0


class TestMockSentimentConfig:
    def test_defaults(self):
        cfg = MockSentimentConfig()
        assert cfg.default_score == 0.0
        assert cfg.default_magnitude == 0.5
        assert cfg.should_fail is False


class TestSerializationRoundtrip:
    def test_kraken_market_config_roundtrip(self):
        original = KrakenMarketConfig(
            base_url="https://api.kraken.com",
            api_key="mykey",
            api_secret="mysecret",
            timeout=15.0,
        )
        json_str = original.model_dump_json()
        restored = KrakenMarketConfig.model_validate_json(json_str)
        assert restored == original
        assert restored.api_key == "mykey"


class TestJsonSchemaGeneration:
    def test_kraken_market_config_schema(self):
        schema = KrakenMarketConfig.model_json_schema()
        assert "properties" in schema
        assert "base_url" in schema["properties"]
        assert "api_key" in schema["properties"]
        assert "timeout" in schema["properties"]

    def test_schema_is_valid_json(self):
        schema = KrakenMarketConfig.model_json_schema()
        # Ensure it round-trips through JSON without error
        json_str = json.dumps(schema)
        parsed = json.loads(json_str)
        assert parsed == schema
