from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from src.core.models import AssetType, Fill, OrderSide, PortfolioSnapshot, Position


class PortfolioManager:
    def __init__(self, initial_cash: Decimal = Decimal("100000")):
        self._cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._realized_pnl: list[Decimal] = []
        self._fills: list[Fill] = []

    async def get_snapshot(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            cash=max(self._cash, Decimal(0)),
            positions=list(self._positions.values()),
            timestamp=datetime.now(timezone.utc),
        )

    async def record_fill(self, fill: Fill) -> None:
        self._fills.append(fill)
        cost = fill.fill_price * fill.quantity
        commission = fill.commission

        if fill.side == OrderSide.BUY:
            self._cash -= cost + commission
            if fill.symbol in self._positions:
                pos = self._positions[fill.symbol]
                total_qty = pos.quantity + fill.quantity
                avg_price = (
                    (pos.avg_entry_price * pos.quantity + fill.fill_price * fill.quantity)
                    / total_qty
                )
                self._positions[fill.symbol] = Position(
                    symbol=fill.symbol,
                    quantity=total_qty,
                    avg_entry_price=avg_price,
                    current_price=fill.fill_price,
                    asset_type=pos.asset_type,
                )
            else:
                self._positions[fill.symbol] = Position(
                    symbol=fill.symbol,
                    quantity=fill.quantity,
                    avg_entry_price=fill.fill_price,
                    current_price=fill.fill_price,
                    asset_type=AssetType.STOCK,
                )
        elif fill.side == OrderSide.SELL:
            self._cash += cost - commission
            if fill.symbol in self._positions:
                pos = self._positions[fill.symbol]
                pnl = (fill.fill_price - pos.avg_entry_price) * fill.quantity
                self._realized_pnl.append(pnl)
                remaining = pos.quantity - fill.quantity
                if remaining <= 0:
                    del self._positions[fill.symbol]
                else:
                    self._positions[fill.symbol] = Position(
                        symbol=fill.symbol,
                        quantity=remaining,
                        avg_entry_price=pos.avg_entry_price,
                        current_price=fill.fill_price,
                        asset_type=pos.asset_type,
                    )

    async def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    async def get_pnl(self, period: str) -> float:
        return float(sum(self._realized_pnl))

    def update_price(self, symbol: str, price: Decimal) -> None:
        if symbol in self._positions:
            pos = self._positions[symbol]
            self._positions[symbol] = Position(
                symbol=pos.symbol,
                quantity=pos.quantity,
                avg_entry_price=pos.avg_entry_price,
                current_price=price,
                asset_type=pos.asset_type,
            )
