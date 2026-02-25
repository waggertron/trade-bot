import os

import pytest

# Ensure JWT_SECRET_KEY is set for all tests that load Settings via from_env/from_yaml.
# Direct AuthSettings construction (e.g. test_config_jwt.py) bypasses this.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests!!")


@pytest.fixture
def settings():
    """Load test settings."""
    from src.core.config import Settings

    return Settings.for_testing()


@pytest.fixture
def db_url(tmp_path):
    """Database URL: uses DATABASE_URL env var if set (e.g. Postgres in CI),
    otherwise falls back to a per-test SQLite database."""
    return os.environ.get(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
    )
