"""Tests for structured JSON logging configuration."""

from __future__ import annotations

import json
import logging

from src.core.logging import configure_logging, get_logger


class TestStructuredLogging:
    def test_configure_logging_returns_logger(self):
        logger = configure_logging("test-app")
        assert logger is not None
        assert logger.name == "test-app"

    def test_log_output_is_valid_json(self, capsys):
        logger = configure_logging("json-test", level=logging.INFO)
        logger.info("hello world")

        captured = capsys.readouterr()
        # Should be parseable JSON
        line = captured.err.strip().split("\n")[-1]
        data = json.loads(line)
        assert data["message"] == "hello world"
        assert data["level"] == "info"
        assert "timestamp" in data

    def test_log_includes_extra_context(self, capsys):
        logger = configure_logging("ctx-test", level=logging.INFO)
        logger.info("trade executed", extra={"symbol": "BTC/USD", "side": "buy"})

        captured = capsys.readouterr()
        line = captured.err.strip().split("\n")[-1]
        data = json.loads(line)
        assert data["symbol"] == "BTC/USD"
        assert data["side"] == "buy"

    def test_get_logger_returns_child(self):
        configure_logging("app")
        child = get_logger("app.submodule")
        assert child.name == "app.submodule"

    def test_error_log_includes_level(self, capsys):
        logger = configure_logging("err-test", level=logging.INFO)
        logger.error("something broke")

        captured = capsys.readouterr()
        line = captured.err.strip().split("\n")[-1]
        data = json.loads(line)
        assert data["level"] == "error"
