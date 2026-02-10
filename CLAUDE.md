# Project Preferences

## Package Manager
- **Always use `uv` for all Python operations** — never venv, pip, or conda directly
- Run commands with: `uv run pytest`, `uv run python`, `uv pip install`, etc.
- Never use `.venv/bin/python` or `.venv/bin/pytest` — always `uv run`

## Tech Stack
- Python 3.12+ with asyncio
- Dependencies managed via `pyproject.toml`
