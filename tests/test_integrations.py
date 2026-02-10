import pytest

from src.integrations.claude_client import ClaudeClient
from src.integrations.ollama_client import OllamaClient


async def test_claude_client_constructs():
    client = ClaudeClient(api_key="test-key", model="claude-sonnet-4-5-20250929")
    assert client.model == "claude-sonnet-4-5-20250929"


async def test_ollama_client_constructs():
    client = OllamaClient(host="http://localhost:11434", model="llama3.2")
    assert client.model == "llama3.2"
