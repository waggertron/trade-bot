# src/agents/research.py
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from src.core.models import ResearchReport


class ResearchManager:
    def __init__(self, claude, ollama):
        self._claude = claude
        self._ollama = ollama

    async def run_research(self, symbols: list[str]) -> list[ResearchReport]:
        tasks = [self._research_symbol(symbol) for symbol in symbols]
        return await asyncio.gather(*tasks)

    async def _research_symbol(self, symbol: str) -> ResearchReport:
        analysis = await self._claude.analyze(
            prompt=f"Analyze the current market outlook for {symbol}. "
                   f"Consider recent earnings, news, and market conditions.",
            system="You are a senior financial analyst. Provide concise, actionable analysis.",
        )
        sentiment = await self._claude.score_sentiment(analysis)

        return ResearchReport(
            symbol=symbol,
            summary=analysis,
            sentiment_score=sentiment,
            timestamp=datetime.now(timezone.utc),
            sources=["claude_analysis"],
        )

    async def score_headline(self, headline: str) -> float:
        return await self._ollama.score_sentiment_fast(headline)
