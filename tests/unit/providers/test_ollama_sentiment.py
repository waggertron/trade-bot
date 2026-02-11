"""Tests for the Ollama sentiment analyzer implementation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.providers.configs import OllamaSentimentConfig
from src.providers.ollama_sentiment import OllamaSentimentAnalyzer
from src.providers.protocols import SentimentAnalyzer
from src.sentiment.models import SentimentResult


@pytest.fixture
def config() -> OllamaSentimentConfig:
    return OllamaSentimentConfig()


@pytest.fixture
def analyzer(config: OllamaSentimentConfig) -> OllamaSentimentAnalyzer:
    return OllamaSentimentAnalyzer(config)


class TestOllamaSentimentAnalyzer:
    """Tests for OllamaSentimentAnalyzer (all using mocked _call_ollama)."""

    def test_creates_with_config_and_name(self, analyzer: OllamaSentimentAnalyzer):
        """Creates with config and name is 'ollama'."""
        assert analyzer.name == "ollama"

    def test_implements_sentiment_analyzer_protocol(
        self, analyzer: OllamaSentimentAnalyzer,
    ):
        """Implements SentimentAnalyzer protocol."""
        assert isinstance(analyzer, SentimentAnalyzer)

    async def test_score_returns_sentiment_result_on_valid_json(
        self, analyzer: OllamaSentimentAnalyzer,
    ):
        """score returns SentimentResult on valid JSON response."""
        mock_response = {
            "message": {
                "content": '{"score": 0.7, "magnitude": 0.8, "reasoning": "positive outlook"}',
            },
        }
        with patch.object(
            analyzer, "_call_ollama", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await analyzer.score("Bitcoin is surging")

        assert isinstance(result, SentimentResult)
        assert result.score == 0.7
        assert result.magnitude == 0.8
        assert result.reasoning == "positive outlook"
        assert result.analyzer == "ollama"

    async def test_score_clamps_out_of_range_values(
        self, analyzer: OllamaSentimentAnalyzer,
    ):
        """score clamps values to valid ranges."""
        mock_response = {
            "message": {
                "content": '{"score": 5.0, "magnitude": -2.0, "reasoning": "extreme"}',
            },
        }
        with patch.object(
            analyzer, "_call_ollama", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await analyzer.score("some text")

        assert result.score == 1.0
        assert result.magnitude == 0.0

    async def test_score_batch_processes_all_texts(
        self, analyzer: OllamaSentimentAnalyzer,
    ):
        """score_batch processes all texts."""
        mock_responses = [
            {
                "message": {
                    "content": '{"score": 0.5, "magnitude": 0.6, "reasoning": "good"}',
                },
            },
            {
                "message": {
                    "content": '{"score": -0.3, "magnitude": 0.4, "reasoning": "bad"}',
                },
            },
            {
                "message": {
                    "content": '{"score": 0.0, "magnitude": 0.1, "reasoning": "neutral"}',
                },
            },
        ]
        with patch.object(
            analyzer, "_call_ollama", new_callable=AsyncMock, side_effect=mock_responses
        ):
            results = await analyzer.score_batch(["text1", "text2", "text3"])

        assert len(results) == 3
        assert results[0].score == 0.5
        assert results[1].score == -0.3
        assert results[2].score == 0.0

    async def test_handles_malformed_response_gracefully(
        self, analyzer: OllamaSentimentAnalyzer,
    ):
        """Handles malformed response gracefully (neutral fallback)."""
        mock_response = {
            "message": {
                "content": "this is not valid json at all",
            },
        }
        with patch.object(
            analyzer, "_call_ollama", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await analyzer.score("some text")

        assert isinstance(result, SentimentResult)
        assert result.score == 0.0
        assert result.magnitude == 0.0
        assert result.reasoning == "Failed to parse Ollama response"
        assert result.analyzer == "ollama"

    async def test_handles_missing_keys_gracefully(
        self, analyzer: OllamaSentimentAnalyzer,
    ):
        """Handles response with missing keys gracefully (neutral fallback)."""
        mock_response = {
            "message": {
                "content": '{"score": 0.5}',
            },
        }
        with patch.object(
            analyzer, "_call_ollama", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await analyzer.score("some text")

        assert result.score == 0.0
        assert result.magnitude == 0.0
        assert result.reasoning == "Failed to parse Ollama response"

    async def test_handles_api_error_gracefully(
        self, analyzer: OllamaSentimentAnalyzer,
    ):
        """Handles API error gracefully (neutral fallback)."""
        with patch.object(
            analyzer,
            "_call_ollama",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("POST", "http://localhost:11434/api/chat"),
                response=httpx.Response(500),
            ),
        ):
            result = await analyzer.score("some text")

        assert isinstance(result, SentimentResult)
        assert result.score == 0.0
        assert result.magnitude == 0.0
        assert result.reasoning == "Failed to parse Ollama response"
        assert result.analyzer == "ollama"

    async def test_handles_connection_error_gracefully(
        self, analyzer: OllamaSentimentAnalyzer,
    ):
        """Handles connection error gracefully (neutral fallback)."""
        with patch.object(
            analyzer,
            "_call_ollama",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await analyzer.score("some text")

        assert isinstance(result, SentimentResult)
        assert result.score == 0.0
        assert result.magnitude == 0.0
        assert result.reasoning == "Failed to parse Ollama response"
        assert result.analyzer == "ollama"
