"""Structured JSON logging configuration."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge extra fields (skip standard LogRecord attributes)
        _standard = {
            "name",
            "msg",
            "args",
            "created",
            "relativeCreated",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "pathname",
            "filename",
            "module",
            "levelname",
            "levelno",
            "msecs",
            "processName",
            "process",
            "threadName",
            "thread",
            "message",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in _standard and not key.startswith("_"):
                entry[key] = value

        if record.exc_info and record.exc_info[1]:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, default=str)


def configure_logging(
    name: str = "trade-bot",
    level: int = logging.INFO,
) -> logging.Logger:
    """Configure structured JSON logging and return the root logger."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates on reconfigure
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    # Don't propagate to root to avoid double-logging
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger by name."""
    return logging.getLogger(name)
