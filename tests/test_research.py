# tests/test_research.py
import pytest
from datetime import datetime, timezone

from src.agents.research import ResearchManager


class MockClaudeClient:
    model = "mock"

    async def analyze(self, prompt, system=""):
        return "Strong earnings beat. Revenue up 15%. Raised full-year guidance."

    async def score_sentiment(self, text):
        return 0.8


class MockOllamaClient:
    model = "mock"

    async def score_sentiment_fast(self, headline):
        if "surge" in headline.lower() or "beat" in headline.lower():
            return 0.7
        return -0.3


@pytest.fixture
def researcher():
    return ResearchManager(
        claude=MockClaudeClient(),
        ollama=MockOllamaClient(),
    )


async def test_run_research(researcher):
    reports = await researcher.run_research(["AAPL"])
    assert len(reports) == 1
    assert reports[0].symbol == "AAPL"
    assert reports[0].sentiment_score == 0.8


async def test_score_headline(researcher):
    score = await researcher.score_headline("AAPL earnings beat expectations")
    assert score == 0.7


async def test_research_multiple_symbols(researcher):
    reports = await researcher.run_research(["AAPL", "MSFT"])
    assert len(reports) == 2
    symbols = {r.symbol for r in reports}
    assert symbols == {"AAPL", "MSFT"}
