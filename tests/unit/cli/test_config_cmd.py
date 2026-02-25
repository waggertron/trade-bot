"""Tests for tradebot config CLI commands."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import yaml
from typer.testing import CliRunner

from src.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

VALID_CONFIG = {
    "mode": "paper",
    "trading": {
        "symbols": {"stocks": ["AAPL"], "crypto": ["BTC/USD"]},
    },
    "risk": {},
    "ai": {},
    "dashboard": {"port": 8080},
}

INVALID_CONFIG = {
    "mode": "invalid_mode",
}


class TestConfigValidate:
    def test_valid_config(self, tmp_path: Path):
        cfg = tmp_path / "settings.yaml"
        cfg.write_text(yaml.dump(VALID_CONFIG))
        result = runner.invoke(app, ["config", "validate", "--config", str(cfg)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_invalid_config(self, tmp_path: Path):
        cfg = tmp_path / "settings.yaml"
        cfg.write_text(yaml.dump(INVALID_CONFIG))
        result = runner.invoke(app, ["config", "validate", "--config", str(cfg)])
        assert result.exit_code == 1

    def test_missing_file(self):
        result = runner.invoke(app, ["config", "validate", "--config", "/nonexistent/path.yaml"])
        assert result.exit_code == 1


class TestConfigShow:
    def test_yaml_output(self, tmp_path: Path):
        cfg = tmp_path / "settings.yaml"
        cfg.write_text(yaml.dump(VALID_CONFIG))
        result = runner.invoke(app, ["config", "show", "--config", str(cfg), "--format", "yaml"])
        assert result.exit_code == 0
        assert "mode" in result.output

    def test_json_output(self, tmp_path: Path):
        cfg = tmp_path / "settings.yaml"
        cfg.write_text(yaml.dump(VALID_CONFIG))
        result = runner.invoke(app, ["config", "show", "--config", str(cfg), "--format", "json"])
        assert result.exit_code == 0
        # Should be parseable JSON
        parsed = json.loads(result.output)
        assert parsed["mode"] == "paper"


class TestConfigSchema:
    def test_known_model_shows_properties(self):
        result = runner.invoke(app, ["config", "schema", "RiskSettings"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "properties" in parsed

    def test_unknown_model_exits_1(self):
        result = runner.invoke(app, ["config", "schema", "NonExistentModel"])
        assert result.exit_code == 1
