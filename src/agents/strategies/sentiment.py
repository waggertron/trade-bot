from __future__ import annotations

from datetime import UTC, datetime

from src.core.models import MarketTick, ResearchReport, Signal, SignalDirection


class SentimentStrategy:
    name = "sentiment"

    def __init__(self, buy_threshold: float = 0.6, sell_threshold: float = -0.6):
        self._buy_threshold = buy_threshold
        self._sell_threshold = sell_threshold

    async def evaluate(
        self,
        symbol: str,
        market_data: list[MarketTick],
        research: list[ResearchReport] | None = None,
    ) -> Signal | None:
        if not research:
            return None

        relevant = [r for r in research if r.symbol == symbol]
        if not relevant:
            return None

        avg_sentiment = sum(r.sentiment_score for r in relevant) / len(relevant)

        if avg_sentiment >= self._buy_threshold:
            direction = SignalDirection.BUY
            confidence = min(avg_sentiment, 1.0)
        elif avg_sentiment <= self._sell_threshold:
            direction = SignalDirection.SELL
            confidence = min(abs(avg_sentiment), 1.0)
        else:
            return None

        summaries = "; ".join(r.summary for r in relevant[:3])

        return Signal(
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            strategy_name=self.name,
            timestamp=datetime.now(UTC),
            reasoning=f"Avg sentiment: {avg_sentiment:.2f}. {summaries}",
        )
