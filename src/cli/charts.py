"""Shared chart utilities for CLI visualization.

Provides terminal-friendly charting helpers built on asciichartpy and plain
ASCII/Unicode.  All functions handle edge cases (empty data, single points,
etc.) gracefully and return plain strings so callers can print or embed them
in Rich panels/tables.

These helpers avoid braille characters and ANSI escape sequences so they
render cleanly in terminals like Warp, iTerm2, and the default macOS Terminal.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import asciichartpy

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Sparkline block characters (ascending height)
# ---------------------------------------------------------------------------
_SPARK_CHARS = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"


def _sanitize(values: Sequence[float | int]) -> list[float]:
    """Convert to floats, filtering out NaN and infinity."""
    return [float(v) for v in values if math.isfinite(float(v))]


# ---------------------------------------------------------------------------
# Simple line chart (asciichartpy wrapper)
# ---------------------------------------------------------------------------


def ascii_line_chart(
    series: Sequence[float | int],
    title: str = "",
    width: int = 60,
    height: int = 12,
) -> str:
    """Render a simple ASCII line chart.

    Parameters
    ----------
    series : sequence of numbers
        Data points to plot.
    title : str
        Optional title displayed above the chart.
    width : int
        Maximum chart width in columns (the library may truncate to fit).
    height : int
        Chart height in rows.

    Returns
    -------
    str
        Multiline string ready for printing.
    """
    if not series:
        return f"{title}\n(no data)" if title else "(no data)"

    data = _sanitize(series)
    if not data:
        return f"{title}\n(no data)" if title else "(no data)"

    # asciichartpy uses "height" for vertical resolution
    cfg = {
        "height": max(3, height),
    }

    # Truncate to requested width if the series is longer
    if len(data) > width:
        data = data[-width:]

    chart = asciichartpy.plot(data, cfg)

    if title:
        return f"{title}\n{chart}"
    return chart


# ---------------------------------------------------------------------------
# Horizontal bar chart (pure ASCII)
# ---------------------------------------------------------------------------

_BAR_CHAR = "\u2588"  # Full block — renders in all terminals


def plotext_bar_chart(
    labels: Sequence[str],
    values: Sequence[float | int],
    title: str = "",
    bar_width: int = 40,
) -> str:
    """Render a horizontal bar chart using plain block characters.

    Parameters
    ----------
    labels : sequence of str
        Category labels.
    values : sequence of numbers
        Corresponding values.
    title : str
        Chart title.
    bar_width : int
        Maximum width of the bar portion in columns.

    Returns
    -------
    str
        Rendered chart as a string.
    """
    if not labels or not values:
        return f"{title}\n(no data)" if title else "(no data)"

    fvals = [float(v) for v in values]
    max_abs = max(abs(v) for v in fvals) if fvals else 1.0
    if max_abs == 0:
        max_abs = 1.0

    label_width = max(len(str(l)) for l in labels)
    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("")

    for label, val in zip(labels, fvals):
        bar_len = int(abs(val) / max_abs * bar_width)
        bar = _BAR_CHAR * max(bar_len, 1)
        sign = "-" if val < 0 else " "
        lines.append(f"  {str(label):>{label_width}}  {sign}{bar} {val:,.2f}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Multi-line chart (asciichartpy wrapper)
# ---------------------------------------------------------------------------


def plotext_multi_line(
    series_dict: dict[str, Sequence[float | int]],
    title: str = "",
) -> str:
    """Render multiple line series on a single ASCII chart via asciichartpy.

    Parameters
    ----------
    series_dict : dict mapping label -> sequence of numbers
        Each entry is one line to plot.
    title : str
        Chart title.

    Returns
    -------
    str
        Rendered chart as a string.
    """
    if not series_dict or not any(series_dict.values()):
        return f"{title}\n(no data)" if title else "(no data)"

    all_series: list[list[float]] = []
    labels: list[str] = []
    for label, data in series_dict.items():
        clean = _sanitize(data)
        if clean:
            all_series.append(clean)
            labels.append(label)

    if not all_series:
        return f"{title}\n(no data)" if title else "(no data)"

    cfg = {"height": 12}
    chart = asciichartpy.plot(all_series, cfg)

    # Build legend line
    legend = "  ".join(labels)
    parts: list[str] = []
    if title:
        parts.append(title)
    parts.append(chart)
    parts.append(f"  Legend: {legend}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Text-based heatmap (plain ASCII table)
# ---------------------------------------------------------------------------

_HEAT_CHARS = " ░▒▓█"


def plotext_heatmap(
    matrix: Sequence[Sequence[float | int]],
    row_labels: Sequence[str] | None = None,
    col_labels: Sequence[str] | None = None,
    title: str = "",
) -> str:
    """Render a heatmap as a plain-text table with numeric values.

    Parameters
    ----------
    matrix : 2-D sequence of numbers
        Row-major data.
    row_labels : optional sequence of str
        Labels for each row.
    col_labels : optional sequence of str
        Labels for each column.
    title : str
        Chart title.

    Returns
    -------
    str
        Rendered chart as a string.
    """
    if not matrix or not matrix[0]:
        return f"{title}\n(no data)" if title else "(no data)"

    fmatrix = [[float(v) for v in row] for row in matrix]
    all_vals = [v for row in fmatrix for v in row]
    lo = min(all_vals)
    hi = max(all_vals)
    span = hi - lo if hi != lo else 1.0

    n_cols = len(fmatrix[0])
    r_labels = list(row_labels) if row_labels else [str(i) for i in range(len(fmatrix))]
    c_labels = list(col_labels) if col_labels else [str(i) for i in range(n_cols)]

    row_w = max(len(l) for l in r_labels)
    col_w = max(max(len(l) for l in c_labels), 6)

    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("")

    # Header row
    header = " " * (row_w + 2) + "  ".join(f"{l:>{col_w}}" for l in c_labels)
    lines.append(header)

    for i, row in enumerate(fmatrix):
        cells: list[str] = []
        for v in row:
            idx = int((v - lo) / span * (len(_HEAT_CHARS) - 1))
            idx = max(0, min(len(_HEAT_CHARS) - 1, idx))
            cells.append(f"{v:>{col_w}.1f}{_HEAT_CHARS[idx]}")
        lines.append(f"{r_labels[i]:>{row_w}}  {'  '.join(cells)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_pct(value: float | int | None) -> str:
    """Return a Rich-markup-friendly colored percentage string.

    Positive values are green, negative values are red, zero/None is dim.

    Parameters
    ----------
    value : float, int, or None
        The percentage value (e.g. 12.5 means 12.5%).

    Returns
    -------
    str
        A Rich-compatible markup string like ``[green]+12.50%[/green]``.
    """
    if value is None:
        return "[dim]N/A[/dim]"
    v = float(value)
    if v > 0:
        return f"[green]+{v:.2f}%[/green]"
    if v < 0:
        return f"[red]{v:.2f}%[/red]"
    return f"[dim]{v:.2f}%[/dim]"


def format_currency(value: float | int | None) -> str:
    """Return a formatted dollar amount string.

    Parameters
    ----------
    value : float, int, or None
        Dollar amount.

    Returns
    -------
    str
        e.g. ``$1,234.56`` or ``-$500.00``.
    """
    if value is None:
        return "N/A"
    v = float(value)
    if v < 0:
        return f"-${abs(v):,.2f}"
    return f"${v:,.2f}"


def spark_line(values: Sequence[float | int]) -> str:
    """Return an inline Unicode sparkline string.

    Uses block characters (U+2581..U+2588) to represent relative magnitudes.

    Parameters
    ----------
    values : sequence of numbers
        Data points.

    Returns
    -------
    str
        A compact sparkline like ``"▁▂▄▇█▅▃▁"``.
    """
    if not values:
        return ""

    nums = _sanitize(values)
    if not nums:
        return ""

    lo = min(nums)
    hi = max(nums)

    # If all values are identical, return a flat mid-height line
    if hi == lo:
        mid = _SPARK_CHARS[len(_SPARK_CHARS) // 2]
        return mid * len(nums)

    span = hi - lo
    max_idx = len(_SPARK_CHARS) - 1
    chars: list[str] = []
    for v in nums:
        # Normalize to 0..1, then map to character index
        idx = round((v - lo) / span * max_idx)
        # Clamp just in case of floating-point edge cases
        idx = max(0, min(max_idx, idx))
        chars.append(_SPARK_CHARS[idx])

    return "".join(chars)
