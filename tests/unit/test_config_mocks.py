"""Tests for the use_mocks config section."""

from __future__ import annotations

from src.core.config import Settings


def test_mock_settings_default_all_true():
    settings = Settings.for_testing()
    assert settings.use_mocks.stock_feed is True
    assert settings.use_mocks.sentiment is True
    assert settings.use_mocks.onchain is True
    assert settings.use_mocks.ml is True
    assert settings.use_mocks.position_sizer is True


def test_mock_settings_can_override():
    settings = Settings.for_testing(
        use_mocks={"stock_feed": False, "ml": False}
    )
    assert settings.use_mocks.stock_feed is False
    assert settings.use_mocks.ml is False
    # Others stay default
    assert settings.use_mocks.sentiment is True
    assert settings.use_mocks.onchain is True
    assert settings.use_mocks.position_sizer is True


def test_mock_settings_from_yaml(tmp_path):
    yaml_content = """\
mode: paper
trading:
  symbols:
    stocks: []
    crypto: ["BTC/USD"]
risk: {}
ai: {}
dashboard:
  port: 8080
use_mocks:
  stock_feed: false
  sentiment: true
  onchain: true
  ml: false
  position_sizer: true
"""
    yaml_path = tmp_path / "settings.yaml"
    yaml_path.write_text(yaml_content)
    settings = Settings.from_yaml(yaml_path)
    assert settings.use_mocks.stock_feed is False
    assert settings.use_mocks.ml is False
    assert settings.use_mocks.sentiment is True
