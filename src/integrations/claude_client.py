from __future__ import annotations

import anthropic


class ClaudeClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def analyze(self, prompt: str, system: str = "") -> str:
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text

    async def score_sentiment(self, text: str) -> float:
        response = await self.analyze(
            prompt=f"Rate the sentiment of this text from -1.0 (very negative) to 1.0 (very positive). "
                   f"Respond with ONLY a number.\n\nText: {text}",
            system="You are a financial sentiment analyzer. Respond with only a float between -1.0 and 1.0.",
        )
        try:
            return max(-1.0, min(1.0, float(response.strip())))
        except ValueError:
            return 0.0
