import tempfile
from pathlib import Path

from src.core.config import Settings, RiskSettings, TradingSettings


def test_load_settings_from_yaml(tmp_path):
    yaml_content = """
mode: paper
trading:
  symbols:
    stocks: ["AAPL"]
    crypto: ["BTC/USD"]
risk:
  max_position_pct: 2.0
  daily_loss_limit_pct: 3.0
  max_open_positions: 10
"""
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(yaml_content)
    settings = Settings.from_yaml(config_file)
    assert settings.mode == "paper"
    assert settings.trading.symbols.stocks == ["AAPL"]
    assert settings.risk.max_position_pct == 2.0


def test_settings_is_paper_mode():
    settings = Settings.for_testing()
    assert settings.is_paper


def test_risk_settings_defaults():
    risk = RiskSettings()
    assert risk.max_position_pct == 2.0
    assert risk.daily_loss_limit_pct == 3.0
    assert risk.max_open_positions == 10
    assert risk.stop_loss_pct == 5.0
    assert risk.trailing_stop_enabled is False


def test_settings_override():
    settings = Settings.for_testing(risk=RiskSettings(max_position_pct=5.0))
    assert settings.risk.max_position_pct == 5.0
