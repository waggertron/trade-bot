import pytest
from pydantic import ValidationError
from src.core.config import (
    RiskSettings, RiskLevel, Settings, TradingSettings,
    SymbolsConfig, AISettings, DashboardSettings,
)


class TestRiskSettingsValidation:
    def test_defaults(self):
        rs = RiskSettings()
        assert rs.max_position_pct == 2.0
        assert rs.max_open_positions == 10
        assert rs.daily_loss_limit_pct == 3.0
        assert rs.stop_loss_pct == 5.0
        assert rs.trailing_stop_enabled is False

    def test_rejects_negative_position_pct(self):
        with pytest.raises(ValidationError):
            RiskSettings(max_position_pct=-1.0)

    def test_rejects_zero_position_pct(self):
        with pytest.raises(ValidationError):
            RiskSettings(max_position_pct=0.0)

    def test_rejects_zero_max_positions(self):
        with pytest.raises(ValidationError):
            RiskSettings(max_open_positions=0)

    def test_rejects_negative_daily_loss_limit(self):
        with pytest.raises(ValidationError):
            RiskSettings(daily_loss_limit_pct=-5.0)

    def test_rejects_position_pct_over_100(self):
        with pytest.raises(ValidationError):
            RiskSettings(max_position_pct=101.0)

    def test_from_risk_level_enum(self):
        rs = RiskSettings.from_risk_level(RiskLevel.CONSERVATIVE)
        assert rs.max_position_pct == 1.0
        assert rs.daily_loss_limit_pct == 2.0
        assert rs.max_open_positions == 5

    def test_from_risk_level_string(self):
        rs = RiskSettings.from_risk_level("aggressive")
        assert rs.max_position_pct == 5.0
        assert rs.max_open_positions == 15

    def test_from_risk_level_with_overrides(self):
        rs = RiskSettings.from_risk_level(RiskLevel.CONSERVATIVE, max_open_positions=3)
        assert rs.max_position_pct == 1.0
        assert rs.max_open_positions == 3

    def test_serialization_roundtrip(self):
        rs = RiskSettings(max_position_pct=3.0, stop_loss_pct=4.0)
        data = rs.model_dump()
        restored = RiskSettings.model_validate(data)
        assert restored == rs

    def test_frozen(self):
        rs = RiskSettings()
        with pytest.raises(ValidationError):
            rs.max_position_pct = 5.0


class TestSymbolsConfig:
    def test_defaults_empty(self):
        sc = SymbolsConfig()
        assert sc.stocks == []
        assert sc.crypto == []

    def test_with_values(self):
        sc = SymbolsConfig(stocks=["AAPL", "MSFT"], crypto=["BTC/USD"])
        assert sc.stocks == ["AAPL", "MSFT"]
        assert sc.crypto == ["BTC/USD"]


class TestTradingSettings:
    def test_defaults(self):
        ts = TradingSettings()
        assert isinstance(ts.symbols, SymbolsConfig)
        assert ts.market_hours == {}

    def test_nested_symbols(self):
        ts = TradingSettings.model_validate({
            "symbols": {"stocks": ["AAPL"], "crypto": ["BTC/USD"]},
            "market_hours": {"stocks_open": "09:30"},
        })
        assert ts.symbols.stocks == ["AAPL"]
        assert ts.market_hours["stocks_open"] == "09:30"


class TestAISettings:
    def test_defaults(self):
        ai = AISettings()
        assert ai.claude_model == "claude-sonnet-4-5-20250929"
        assert ai.ollama_model == "llama3.2"


class TestDashboardSettings:
    def test_defaults(self):
        ds = DashboardSettings()
        assert ds.host == "0.0.0.0"
        assert ds.port == 8080

    def test_rejects_zero_port(self):
        with pytest.raises(ValidationError):
            DashboardSettings(port=0)

    def test_rejects_port_over_65535(self):
        with pytest.raises(ValidationError):
            DashboardSettings(port=70000)


class TestSettingsFromYaml:
    def test_loads_from_yaml(self, tmp_path):
        yaml_content = """
mode: paper
trading:
  symbols:
    stocks: [AAPL]
    crypto: [BTC/USD]
  market_hours:
    stocks_open: "09:30"
    stocks_close: "16:00"
    timezone: US/Eastern
risk:
  max_position_pct: 2.0
  daily_loss_limit_pct: 3.0
  max_open_positions: 10
  stop_loss_pct: 5.0
ai:
  claude_model: claude-sonnet-4-5-20250929
  ollama_model: llama3.2
dashboard:
  host: 0.0.0.0
  port: 8080
"""
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml_content)
        settings = Settings.from_yaml(config_file)
        assert settings.mode == "paper"
        assert settings.trading.symbols.stocks == ["AAPL"]
        assert settings.risk.max_position_pct == 2.0
        assert settings.dashboard.port == 8080

    def test_rejects_invalid_yaml(self, tmp_path):
        config_file = tmp_path / "settings.yaml"
        config_file.write_text("risk:\n  max_position_pct: -5")
        with pytest.raises(ValidationError):
            Settings.from_yaml(config_file)

    def test_rejects_invalid_mode(self, tmp_path):
        config_file = tmp_path / "settings.yaml"
        config_file.write_text("mode: invalid_mode")
        with pytest.raises(ValidationError):
            Settings.from_yaml(config_file)

    def test_for_testing(self):
        settings = Settings.for_testing()
        assert settings.mode == "paper"
        assert isinstance(settings.risk, RiskSettings)
        assert isinstance(settings.trading, TradingSettings)

    def test_for_testing_is_paper(self):
        settings = Settings.for_testing()
        assert settings.is_paper

    def test_for_testing_with_risk_override(self):
        settings = Settings.for_testing(
            risk={"max_position_pct": 5.0, "max_open_positions": 3}
        )
        assert settings.risk.max_position_pct == 5.0
        assert settings.risk.max_open_positions == 3

    def test_settings_frozen(self):
        settings = Settings.for_testing()
        with pytest.raises(ValidationError):
            settings.mode = "live"

    def test_settings_serialization_roundtrip(self):
        settings = Settings.for_testing()
        data = settings.model_dump()
        restored = Settings.model_validate(data)
        assert restored == settings
