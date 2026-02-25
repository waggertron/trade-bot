"""Tests for chart utilities."""

from __future__ import annotations

from src.cli.charts import plotext_multi_line


def test_multi_line_chart_contains_ansi_color_codes():
    """Multi-line chart with multiple series should contain ANSI color escapes."""
    series = {
        "P5": [100, 90, 85],
        "Median": [100, 110, 120],
        "P95": [100, 130, 150],
    }
    chart = plotext_multi_line(series, title="Test")
    # ANSI escape codes start with \x1b[
    assert "\x1b[" in chart, "Expected ANSI color codes in multi-line chart"


def test_multi_line_chart_legend_has_colored_markers():
    """Legend should include colored markers matching each series."""
    series = {
        "Alpha": [10, 20, 30],
        "Beta": [5, 15, 25],
    }
    chart = plotext_multi_line(series, title="Test")
    # Legend should contain both labels with color indicators
    assert "Alpha" in chart
    assert "Beta" in chart
    # Each legend entry should have an ANSI-colored marker before the label
    legend_line = next(line for line in chart.split("\n") if "Legend:" in line)
    assert "\x1b[" in legend_line, "Legend should have colored markers"


def test_single_series_still_works():
    """A single series should render without errors."""
    series = {"Only": [10, 20, 30]}
    chart = plotext_multi_line(series, title="Single")
    assert "Only" in chart
    assert "Single" in chart
