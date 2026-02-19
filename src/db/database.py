from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.db.models import (
    ArticleRecord,
    FeedRecord,
    OHLCRecord,
    SentimentScoreRecord,
    SignalRecord,
    TradeRecord,
)

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

ohlc_bars_table = sa.Table(
    "ohlc_bars", metadata,
    sa.Column("symbol", sa.String, nullable=False),
    sa.Column("interval", sa.String, nullable=False),
    sa.Column("timestamp", sa.Integer, nullable=False),
    sa.Column("open", sa.String, nullable=False),
    sa.Column("high", sa.String, nullable=False),
    sa.Column("low", sa.String, nullable=False),
    sa.Column("close", sa.String, nullable=False),
    sa.Column("volume", sa.String, nullable=False),
    sa.Column("source", sa.String, nullable=False),
    sa.PrimaryKeyConstraint("symbol", "interval", "timestamp"),
)


feeds_table = sa.Table(
    "feeds", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("url", sa.String, nullable=False, unique=True),
    sa.Column("feed_type", sa.String, nullable=False),
    sa.Column("category", sa.String, nullable=False),
    sa.Column("auth_type", sa.String, nullable=False, server_default="free"),
    sa.Column("rate_limit_rpm", sa.Integer, server_default="60"),
    sa.Column("enabled", sa.Boolean, server_default=sa.text("1")),
    sa.Column("last_fetched_at", sa.DateTime, nullable=True),
    sa.Column("created_at", sa.DateTime, nullable=False),
)

articles_table = sa.Table(
    "articles", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("content_hash", sa.String, nullable=False, unique=True),
    sa.Column("title", sa.String, nullable=False),
    sa.Column("body", sa.String, server_default=""),
    sa.Column("source", sa.String, nullable=False),
    sa.Column("url", sa.String, server_default=""),
    sa.Column("published_at", sa.DateTime, nullable=False),
    sa.Column("fetched_at", sa.DateTime, nullable=False),
    sa.Column("feed_id", sa.String, sa.ForeignKey("feeds.id"), nullable=True),
    sa.Column("created_at", sa.DateTime, nullable=False),
)

article_symbols_table = sa.Table(
    "article_symbols", metadata,
    sa.Column("article_id", sa.String, sa.ForeignKey("articles.id"), nullable=False),
    sa.Column("symbol", sa.String, nullable=False),
    sa.PrimaryKeyConstraint("article_id", "symbol"),
)

sentiment_scores_table = sa.Table(
    "sentiment_scores", metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("article_id", sa.String, sa.ForeignKey("articles.id"), nullable=False),
    sa.Column("score", sa.Float, nullable=False),
    sa.Column("magnitude", sa.Float, nullable=False),
    sa.Column("reasoning", sa.String, nullable=True),
    sa.Column("analyzer", sa.String, nullable=False),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.UniqueConstraint("article_id", "analyzer"),
)


class Database:
    def __init__(self, url: str) -> None:
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

    async def load_ohlc_bars(self, records: list[OHLCRecord]) -> int:
        """Bulk INSERT OR REPLACE OHLC records in batches of 1000."""
        if not records:
            return 0
        batch_size = 1000
        total = 0
        async with self._engine.begin() as conn:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                # Use SQLite dialect INSERT OR REPLACE via raw text
                for rec in batch:
                    await conn.execute(
                        sa.text(
                            "INSERT OR REPLACE INTO ohlc_bars "
                            "(symbol, interval, timestamp, open, high, low, close, volume, source) "
                            "VALUES (:symbol, :interval, :timestamp, :open, :high, :low, "
                            ":close, :volume, :source)"
                        ),
                        {
                            "symbol": rec.symbol,
                            "interval": rec.interval,
                            "timestamp": rec.timestamp,
                            "open": rec.open,
                            "high": rec.high,
                            "low": rec.low,
                            "close": rec.close,
                            "volume": rec.volume,
                            "source": rec.source,
                        },
                    )
                total += len(batch)
        return total

    async def query_ohlc_bars(
        self,
        symbol: str | None = None,
        interval: str | None = None,
        start_ts: int | None = None,
        end_ts: int | None = None,
        source: str | None = None,
        limit: int = 10000,
    ) -> list[OHLCRecord]:
        """Query OHLC bars with optional filters."""
        query = ohlc_bars_table.select().order_by(ohlc_bars_table.c.timestamp.asc())
        if symbol is not None:
            query = query.where(ohlc_bars_table.c.symbol == symbol)
        if interval is not None:
            query = query.where(ohlc_bars_table.c.interval == interval)
        if start_ts is not None:
            query = query.where(ohlc_bars_table.c.timestamp >= start_ts)
        if end_ts is not None:
            query = query.where(ohlc_bars_table.c.timestamp <= end_ts)
        if source is not None:
            query = query.where(ohlc_bars_table.c.source == source)
        query = query.limit(limit)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
        return [OHLCRecord(**r._asdict()) for r in rows]

    async def count_ohlc_bars(
        self,
        symbol: str | None = None,
        interval: str | None = None,
    ) -> int:
        """Count OHLC bars with optional filters."""
        query = sa.select(sa.func.count()).select_from(ohlc_bars_table)
        if symbol is not None:
            query = query.where(ohlc_bars_table.c.symbol == symbol)
        if interval is not None:
            query = query.where(ohlc_bars_table.c.interval == interval)
        async with self._engine.connect() as conn:
            result = await conn.execute(query)
            return int(result.scalar() or 0)
