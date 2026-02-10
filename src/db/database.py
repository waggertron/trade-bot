from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import TradeRecord, SignalRecord

metadata = sa.MetaData()

trades_table = sa.Table(
    "trades", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("symbol", sa.String, nullable=False),
    sa.Column("side", sa.String, nullable=False),
    sa.Column("quantity", sa.String, nullable=False),
    sa.Column("price", sa.String, nullable=False),
    sa.Column("commission", sa.String, nullable=False),
    sa.Column("strategy", sa.String, nullable=False),
    sa.Column("paper", sa.Boolean, nullable=False),
    sa.Column("timestamp", sa.DateTime, nullable=False),
)

signals_table = sa.Table(
    "signals", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("symbol", sa.String, nullable=False),
    sa.Column("direction", sa.String, nullable=False),
    sa.Column("confidence", sa.Float, nullable=False),
    sa.Column("strategy", sa.String, nullable=False),
    sa.Column("reasoning", sa.String, nullable=False),
    sa.Column("timestamp", sa.DateTime, nullable=False),
)


class Database:
    def __init__(self, url: str):
        self._engine = create_async_engine(url)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def initialize(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()

    async def save_trade(self, trade: TradeRecord) -> str:
        async with self._engine.begin() as conn:
            await conn.execute(trades_table.insert().values(
                id=trade.id, symbol=trade.symbol, side=trade.side,
                quantity=trade.quantity, price=trade.price,
                commission=trade.commission, strategy=trade.strategy,
                paper=trade.paper, timestamp=trade.timestamp,
            ))
        return trade.id

    async def get_trade(self, trade_id: str) -> TradeRecord | None:
        async with self._engine.connect() as conn:
            row = (await conn.execute(
                trades_table.select().where(trades_table.c.id == trade_id)
            )).first()
        if row is None:
            return None
        return TradeRecord(**row._asdict())

    async def list_trades(
        self, strategy: str | None = None, limit: int = 100,
    ) -> list[TradeRecord]:
        query = trades_table.select().order_by(trades_table.c.timestamp.desc()).limit(limit)
        if strategy:
            query = query.where(trades_table.c.strategy == strategy)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
        return [TradeRecord(**r._asdict()) for r in rows]

    async def save_signal(self, signal: SignalRecord) -> str:
        async with self._engine.begin() as conn:
            await conn.execute(signals_table.insert().values(
                id=signal.id, symbol=signal.symbol, direction=signal.direction,
                confidence=signal.confidence, strategy=signal.strategy,
                reasoning=signal.reasoning, timestamp=signal.timestamp,
            ))
        return signal.id

    async def list_signals(self, limit: int = 100) -> list[SignalRecord]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(
                signals_table.select().order_by(signals_table.c.timestamp.desc()).limit(limit)
            )).fetchall()
        return [SignalRecord(**r._asdict()) for r in rows]
