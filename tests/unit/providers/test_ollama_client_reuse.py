"""Tests that OllamaSentimentAnalyzer reuses a shared httpx client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.providers.configs import OllamaSentimentConfig
from src.providers.ollama_sentiment import OllamaSentimentAnalyzer


@pytest.fixture
def analyzer():
    config = OllamaSentimentConfig(base_url="http://localhost:11434", model="llama3")
    return OllamaSentimentAnalyzer(config)


class TestOllamaClientReuse:
    async def test_does_not_create_client_per_call(self, analyzer: OllamaSentimentAnalyzer):
        """Multiple score() calls should NOT create a new httpx.AsyncClient each time."""
        response_data = {
            "message": {
                "content": json.dumps({"score": 0.5, "magnitude": 0.8, "reasoning": "positive"})
            }
        }

        # Track how many AsyncClient instances are created
        with patch("src.providers.ollama_sentiment.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json.return_value = response_data
            mock_response.raise_for_status = AsyncMock()
            mock_client.post.return_value = mock_response

            mock_cls.return_value = mock_client
            # Make it work as async context manager too
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            await analyzer.score("Test text 1")
            await analyzer.score("Test text 2")
            await analyzer.score("Test text 3")

            # Old behavior: 3 calls = 3 AsyncClient() constructions
            # New behavior: should create at most 1 client (shared)
            assert mock_cls.call_count <= 1, (
                f"httpx.AsyncClient created {mock_cls.call_count} times — "
                "should reuse a shared client"
            )

    async def test_client_is_closeable(self, analyzer: OllamaSentimentAnalyzer):
        """Analyzer should provide a way to close the shared client."""
        assert hasattr(analyzer, "close"), "Analyzer should have a close() method"

    async def test_close_disposes_client(self, analyzer: OllamaSentimentAnalyzer):
        """Calling close() should dispose the shared httpx client."""
        response_data = {
            "message": {
                "content": json.dumps({"score": 0.0, "magnitude": 0.5, "reasoning": "neutral"})
            }
        }

        with patch("src.providers.ollama_sentiment.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.json.return_value = response_data
            mock_response.raise_for_status = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_cls.return_value = mock_client
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            # Trigger client creation
            await analyzer.score("Test text")
            # Close should call aclose on the client
            await analyzer.close()

            mock_client.aclose.assert_called_once()
