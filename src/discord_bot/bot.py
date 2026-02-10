from __future__ import annotations

from decimal import Decimal

from src.core.models import Fill, PortfolioSnapshot


def format_trade_alert(fill: Fill, strategy: str = "", reasoning: str = "") -> str:
    side = fill.side.value.upper()
    lines = [
        f"**{side} {fill.symbol}**",
        f"Qty: {fill.quantity} @ ${fill.fill_price}",
        f"Commission: ${fill.commission}",
    ]
    if strategy:
        lines.append(f"Strategy: {strategy}")
    if reasoning:
        lines.append(f"Reasoning: {reasoning}")
    return "\n".join(lines)


def format_portfolio_status(snapshot: PortfolioSnapshot) -> str:
    lines = [
        f"**Portfolio Status**",
        f"Cash: ${snapshot.cash:,.2f}",
        f"Total Value: ${snapshot.total_value:,.2f}",
        f"Positions: {len(snapshot.positions)}",
        "",
    ]
    for pos in snapshot.positions:
        pnl = pos.unrealized_pnl
        pnl_str = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
        lines.append(f"  {pos.symbol}: {pos.quantity} shares @ ${pos.avg_entry_price} ({pnl_str})")
    return "\n".join(lines)


class TradeBot:
    def __init__(self, token: str, channel_id: int):
        self._token = token
        self._channel_id = channel_id
        self._client = None

    async def start(self) -> None:
        import discord

        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_ready():
            print(f"Discord bot connected as {self._client.user}")

        await self._client.start(self._token)

    async def send_alert(self, message: str) -> None:
        if self._client is None:
            return
        channel = self._client.get_channel(self._channel_id)
        if channel:
            await channel.send(message)

    async def stop(self) -> None:
        if self._client:
            await self._client.close()
