"""Ollama-based sentiment analyzer.

Uses a local Ollama instance to score financial text sentiment.
This is the first real (non-mock) implementation of the SentimentAnalyzer protocol.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from src.providers.configs import OllamaSentimentConfig
from src.sentiment.models import SentimentResult

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """Analyze the sentiment of the following financial text.
Return ONLY a JSON object with these fields:
- "score": float from -1.0 (very negative) to 1.0 (very positive)
- "magnitude": float from 0.0 (uncertain) to 1.0 (very confident)
- "reasoning": brief explanation

Text: {text}

JSON:"""


class OllamaSentimentAnalyzer:
    """Sentiment analyzer backed by a local Ollama LLM.

    Sends a structured prompt to the Ollama chat API and parses the
    JSON response into a ``SentimentResult``.  On any failure the
    analyzer returns a neutral fallback (score=0, magnitude=0).
    """

    def __init__(self, config: OllamaSentimentConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "ollama"

    async def score(self, text: str) -> SentimentResult:
        """Score a single piece of text for financial sentiment."""
        try:
            prompt = PROMPT_TEMPLATE.format(text=text)
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
        except (json.JSONDecodeError, KeyError, ValueError, TypeError, httpx.HTTPError):
            logger.warning("Failed to parse Ollama response, returning neutral fallback")
            return SentimentResult(
                score=0.0,
                magnitude=0.0,
                timestamp=datetime.now(timezone.utc),
                reasoning="Failed to parse Ollama response",
                analyzer="ollama",
            )

    async def score_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Score multiple texts sequentially."""
        results: list[SentimentResult] = []
        for text in texts:
            results.append(await self.score(text))
        return results

    async def _call_ollama(self, prompt: str) -> dict:
        """Make an HTTP POST to the Ollama chat API."""
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
