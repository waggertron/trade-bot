"""Tests for environment-based configuration."""

from __future__ import annotations

from src.core.config import Settings


class TestFromEnv:
    def test_creates_settings_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("TRADE_BOT_MODE", "paper")
        monkeypatch.setenv("JWT_SECRET_KEY", "env-secret-123-that-is-32-chars!")

        settings = Settings.from_env()

        assert settings.mode == "paper"
        assert settings.auth.jwt_secret_key == "env-secret-123-that-is-32-chars!"

    def test_defaults_to_paper_mode(self, monkeypatch):
        monkeypatch.delenv("TRADE_BOT_MODE", raising=False)
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-char!")

        settings = Settings.from_env()

        assert settings.mode == "paper"

    def test_reads_crypto_symbols_from_env(self, monkeypatch):
        monkeypatch.setenv("TRADE_BOT_CRYPTO_SYMBOLS", "BTC/USD,ETH/USD")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-char!")

        settings = Settings.from_env()

        assert settings.trading.symbols.crypto == ["BTC/USD", "ETH/USD"]

    def test_reads_stock_symbols_from_env(self, monkeypatch):
        monkeypatch.setenv("TRADE_BOT_STOCK_SYMBOLS", "AAPL,GOOG,MSFT")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-char!")

        settings = Settings.from_env()

        assert settings.trading.symbols.stocks == ["AAPL", "GOOG", "MSFT"]

    def test_reads_dashboard_port_from_env(self, monkeypatch):
        monkeypatch.setenv("TRADE_BOT_DASHBOARD_PORT", "9090")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-char!")

        settings = Settings.from_env()

        assert settings.dashboard.port == 9090

    def test_from_env_works_without_yaml_file(self, monkeypatch):
        """Settings should be constructable purely from env vars."""
        monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-char!")

        settings = Settings.from_env()

        assert isinstance(settings, Settings)
        assert settings.is_paper is True

    def test_yaml_overrides_env_when_both_exist(self, tmp_path, monkeypatch):
        """from_yaml should still work and ignore env-only fields."""
        yaml_content = "mode: paper\ntrading:\n  symbols:\n    crypto:\n      - BTC/USD\n"
        yaml_file = tmp_path / "settings.yaml"
        yaml_file.write_text(yaml_content)
        monkeypatch.setenv("JWT_SECRET_KEY", "env-secret-for-yaml-override-test!")

        settings = Settings.from_yaml(yaml_file)

        assert settings.mode == "paper"
        assert settings.auth.jwt_secret_key == "env-secret-for-yaml-override-test!"
