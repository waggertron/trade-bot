"""Tests that Database accepts and applies connection pool configuration."""

from __future__ import annotations

from src.db.database import Database


class TestPoolConfig:
    def test_default_pool_settings(self, tmp_path):
        """Database should have sensible pool defaults."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
        db = Database(url)
        assert db._engine is not None

    def test_custom_pool_size(self, tmp_path):
        """Database should accept pool_size parameter."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
        db = Database(url, pool_size=20)
        # For SQLite, pool_size is accepted but may not apply (StaticPool)
        # The important thing is the parameter is accepted without error
        assert db._engine is not None

    def test_custom_max_overflow(self, tmp_path):
        """Database should accept max_overflow parameter."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
        db = Database(url, max_overflow=30)
        assert db._engine is not None

    def test_custom_pool_recycle(self, tmp_path):
        """Database should accept pool_recycle parameter."""
        url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
        db = Database(url, pool_recycle=1800)
        assert db._engine is not None

    def test_pool_settings_applied_to_postgres_style_url(self):
        """For non-SQLite URLs, pool settings should be forwarded to engine."""
        # Use a mock URL that won't actually connect — just verify engine creation
        url = "postgresql+asyncpg://user:pass@localhost/testdb"
        db = Database(url, pool_size=15, max_overflow=25, pool_recycle=3600)
        pool = db._engine.pool
        assert pool.size() == 15
        assert pool._max_overflow == 25
        assert pool._recycle == 3600
