"""Portfolio panel for the TUI dashboard."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Label, Sparkline, Static
from textual import work


class PortfolioPanel(Static):
    """Shows portfolio summary, positions table, and equity sparkline."""

    DEFAULT_CSS = """
    PortfolioPanel {
        padding: 1 2;
    }
    PortfolioPanel .section-title {
        text-style: bold;
        margin-bottom: 1;
    }
    PortfolioPanel DataTable {
        height: auto;
        max-height: 20;
    }
    PortfolioPanel Sparkline {
        height: 3;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Portfolio Overview", classes="section-title")
            yield Label("Total Value: [dim]loading...[/dim]", id="pf-total")
            yield Label("Cash: [dim]...[/dim]", id="pf-cash")
            yield Label("P&L: [dim]...[/dim]", id="pf-pnl")
            yield Label("")
            yield Label("Positions", classes="section-title")
            table = DataTable(id="pf-positions")
            table.add_columns("Symbol", "Qty", "Avg Cost", "Current", "P&L %")
            yield table
            yield Label("Equity Curve", classes="section-title")
            yield Sparkline([], id="pf-sparkline")

    def _update_label(self, selector: str, text: str) -> None:
        try:
            self.query_one(selector, Label).update(text)
        except Exception:
            pass

    @work(exclusive=True)
    async def refresh_data(self) -> None:
        """Fetch portfolio data from the API."""
        api = self.app.api_client  # type: ignore[attr-defined]

        try:
            portfolio = await api.get_portfolio()
            total = portfolio.get("total_value", 0)
            cash = portfolio.get("cash", 0)
            self._update_label("#pf-total", f"Total Value: [bold]${total:,.2f}[/bold]")
            self._update_label("#pf-cash", f"Cash: ${cash:,.2f}")
        except Exception:
            self._update_label("#pf-total", "Total Value: [red]error[/red]")

        try:
            pnl_data = await api.get_pnl()
            pnl = pnl_data.get("unrealized_pnl", 0)
            color = "green" if pnl >= 0 else "red"
            self._update_label("#pf-pnl", f"P&L: [{color}]${pnl:,.2f}[/{color}]")
        except Exception:
            pass

        try:
            positions = await api.get_positions()
            table = self.query_one("#pf-positions", DataTable)
            table.clear()
            for pos in positions:
                table.add_row(
                    str(pos.get("symbol", "")),
                    str(pos.get("quantity", 0)),
                    f"${pos.get('avg_cost', 0):,.2f}",
                    f"${pos.get('current_price', 0):,.2f}",
                    f"{pos.get('pnl_pct', 0):.2f}%",
                )
        except Exception:
            pass

        try:
            curve_data = await api.get_equity_curve()
            points = curve_data.get("curve", [])
            if points:
                self.query_one("#pf-sparkline", Sparkline).data = points
        except Exception:
            pass
