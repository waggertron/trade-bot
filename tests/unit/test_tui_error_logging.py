"""Tests that TUI panels and CLI commands log exceptions instead of swallowing them."""

from __future__ import annotations


def test_portfolio_panel_has_no_bare_except_pass():
    """portfolio.py should not contain 'except Exception:\\n            pass'."""
    from pathlib import Path

    source = Path("src/cli/tui/panels/portfolio.py").read_text()
    # Allow "except Exception:" but it should be followed by logger, not pass
    lines = source.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "except Exception:":
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            assert next_line != "pass", (
                f"portfolio.py:{i + 1} has bare 'except Exception: pass' — "
                "should log the exception instead"
            )


def test_risk_panel_has_no_bare_except_pass():
    """risk.py should not contain 'except Exception:\\n            pass'."""
    from pathlib import Path

    source = Path("src/cli/tui/panels/risk.py").read_text()
    lines = source.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "except Exception:":
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            assert next_line != "pass", f"risk.py:{i + 1} has bare 'except Exception: pass'"


def test_system_panel_has_no_bare_except_pass():
    """system.py should not contain 'except Exception:\\n            pass'."""
    from pathlib import Path

    source = Path("src/cli/tui/panels/system.py").read_text()
    lines = source.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "except Exception:":
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            assert next_line != "pass", f"system.py:{i + 1} has bare 'except Exception: pass'"


def test_simulation_panel_has_no_bare_except_pass():
    """simulation.py should not contain 'except Exception:\\n            pass'."""
    from pathlib import Path

    source = Path("src/cli/tui/panels/simulation.py").read_text()
    lines = source.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "except Exception:":
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            assert next_line != "pass", f"simulation.py:{i + 1} has bare 'except Exception: pass'"


def test_backtest_cmd_has_no_bare_except_pass():
    """backtest_cmd.py should not contain 'except Exception:\\n        pass'."""
    from pathlib import Path

    source = Path("src/cli/backtest_cmd.py").read_text()
    lines = source.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "except Exception:":
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            assert next_line != "pass", f"backtest_cmd.py:{i + 1} has bare 'except Exception: pass'"


def test_portfolio_cmd_has_no_bare_except_pass():
    """portfolio_cmd.py should not contain 'except Exception:\\n        pass'."""
    from pathlib import Path

    source = Path("src/cli/portfolio_cmd.py").read_text()
    lines = source.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "except Exception:":
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            assert next_line != "pass", (
                f"portfolio_cmd.py:{i + 1} has bare 'except Exception: pass'"
            )
