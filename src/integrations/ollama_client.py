from __future__ import annotations

import httpx


class OllamaClient:
    def __init__(self, host: str = "http://localhost:11434", model: str = "llama3.2"):
        self._host = host.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(base_url=self._host, timeout=30.0)

    async def generate(self, prompt: str, system: str = "") -> str:
        response = await self._client.post(
            "/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "system": system,
                "stream": False,
            },
        )
        response.raise_for_status()
        return response.json()["response"]

    async def score_sentiment_fast(self, headline: str) -> float:
        response = await self.generate(
            prompt=f"Rate sentiment -1.0 to 1.0. Only output a number.\n{headline}",
            system="Financial sentiment scorer. Output only a float.",
        )
        try:
            return max(-1.0, min(1.0, float(response.strip())))
        except ValueError:
            return 0.0

    async def close(self) -> None:
        await self._client.aclose()
