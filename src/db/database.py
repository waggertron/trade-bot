from __future__ import annotations

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.db.models import (
    ArticleRecord,
    FeedRecord,
    OAuthAccountRecord,
    OHLCRecord,
    SentimentScoreRecord,
    SignalRecord,
    TradeRecord,
    UserRecord,
    UserSettingsRecord,
)

metadata = sa.MetaData()

users_table = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("email", sa.String, nullable=False, unique=True, index=True),
    sa.Column("hashed_password", sa.String, nullable=True),
    sa.Column("name", sa.String, nullable=False, server_default=""),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.false()),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("updated_at", sa.DateTime, nullable=False),
)

oauth_accounts_table = sa.Table(
    "oauth_accounts",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("user_id", sa.String, sa.ForeignKey("users.id"), nullable=False, index=True),
    sa.Column("provider", sa.String, nullable=False),
    sa.Column("provider_user_id", sa.String, nullable=False),
    sa.Column("email", sa.String, nullable=False, server_default=""),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.UniqueConstraint("provider", "provider_user_id"),
)

user_settings_table = sa.Table(
    "user_settings",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column(
        "user_id",
        sa.String,
        sa.ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    ),
    sa.Column("mode", sa.String, nullable=False, server_default="paper"),
    sa.Column("risk_preset", sa.String, nullable=False, server_default=""),
    sa.Column("symbols_config", sa.String, nullable=False, server_default=""),
    sa.Column("strategy_weights", sa.String, nullable=False, server_default=""),
    sa.Column("created_at", sa.DateTime, nullable=False),
    sa.Column("updated_at", sa.DateTime, nullable=False),
)

trades_table = sa.Table(
    "trades",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("user_id", sa.String, sa.ForeignKey("users.id"), nullable=True, index=True),
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
    "signals",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("user_id", sa.String, sa.ForeignKey("users.id"), nullable=True, index=True),
    sa.Column("symbol", sa.String, nullable=False),
    sa.Column("direction", sa.String, nullable=False),
    sa.Column("confidence", sa.Float, nullable=False),
    sa.Column("strategy", sa.String, nullable=False),
    sa.Column("reasoning", sa.String, nullable=False),
    sa.Column("timestamp", sa.DateTime, nullable=False),
)

ohlc_bars_table = sa.Table(
    "ohlc_bars",
    metadata,
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
    "feeds",
    metadata,
    sa.Column("id", sa.String, primary_key=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("url", sa.String, nullable=False, unique=True),
    sa.Column("feed_type", sa.String, nullable=False),
    sa.Column("category", sa.String, nullable=False),
    sa.Column("auth_type", sa.String, nullable=False, server_default="free"),
    sa.Column("rate_limit_rpm", sa.Integer, server_default="60"),
    sa.Column("enabled", sa.Boolean, server_default=sa.true()),
    sa.Column("last_fetched_at", sa.DateTime, nullable=True),
    sa.Column("created_at", sa.DateTime, nullable=False),
)

articles_table = sa.Table(
    "articles",
    metadata,
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
    "article_symbols",
    metadata,
    sa.Column("article_id", sa.String, sa.ForeignKey("articles.id"), nullable=False),
    sa.Column("symbol", sa.String, nullable=False),
    sa.PrimaryKeyConstraint("article_id", "symbol"),
)

sentiment_scores_table = sa.Table(
    "sentiment_scores",
    metadata,
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

    async def initialize(self, *, create_all: bool = True) -> None:
        """Initialize database. Use create_all=True for tests, False when Alembic manages schema."""
        if create_all:
            async with self._engine.begin() as conn:
                await conn.run_sync(metadata.create_all)

    async def close(self) -> None:
        await self._engine.dispose()

    async def check_health(self) -> bool:
        """Check database connectivity by executing a simple query."""
        async with self._engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        return True

    # -- User CRUD -------------------------------------------------------------

    async def create_user(self, user: UserRecord) -> str:
        async with self._engine.begin() as conn:
            await conn.execute(
                users_table.insert().values(
                    id=user.id,
                    email=user.email,
                    hashed_password=user.hashed_password,
                    name=user.name,
                    is_active=user.is_active,
                    is_verified=user.is_verified,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                )
            )
        return user.id

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(users_table.select().where(users_table.c.email == email))
            ).first()
        if row is None:
            return None
        return UserRecord(**row._asdict())

    async def get_user_by_id(self, user_id: str) -> UserRecord | None:
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(users_table.select().where(users_table.c.id == user_id))
            ).first()
        if row is None:
            return None
        return UserRecord(**row._asdict())

    async def update_user(self, user_id: str, **fields: object) -> None:
        if not fields:
            return
        fields["updated_at"] = datetime.now(UTC)
        async with self._engine.begin() as conn:
            await conn.execute(
                users_table.update().where(users_table.c.id == user_id).values(**fields)
            )

    # -- OAuth Account CRUD ----------------------------------------------------

    async def link_oauth_account(self, account: OAuthAccountRecord) -> str:
        async with self._engine.begin() as conn:
            await conn.execute(
                oauth_accounts_table.insert().values(
                    id=account.id,
                    user_id=account.user_id,
                    provider=account.provider,
                    provider_user_id=account.provider_user_id,
                    email=account.email,
                    created_at=account.created_at,
                )
            )
        return account.id

    async def get_user_by_oauth(
        self,
        provider: str,
        provider_user_id: str,
    ) -> UserRecord | None:
        query = (
            sa.select(users_table)
            .join(oauth_accounts_table, users_table.c.id == oauth_accounts_table.c.user_id)
            .where(oauth_accounts_table.c.provider == provider)
            .where(oauth_accounts_table.c.provider_user_id == provider_user_id)
        )
        async with self._engine.connect() as conn:
            row = (await conn.execute(query)).first()
        if row is None:
            return None
        return UserRecord(**row._asdict())

    # -- User Settings CRUD ----------------------------------------------------

    async def save_user_settings(self, settings: UserSettingsRecord) -> str:
        async with self._engine.begin() as conn:
            await conn.execute(
                user_settings_table.insert().values(
                    id=settings.id,
                    user_id=settings.user_id,
                    mode=settings.mode,
                    risk_preset=settings.risk_preset,
                    symbols_config=settings.symbols_config,
                    strategy_weights=settings.strategy_weights,
                    created_at=settings.created_at,
                    updated_at=settings.updated_at,
                )
            )
        return settings.id

    async def get_user_settings(self, user_id: str) -> UserSettingsRecord | None:
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(
                    user_settings_table.select().where(user_settings_table.c.user_id == user_id)
                )
            ).first()
        if row is None:
            return None
        return UserSettingsRecord(**row._asdict())

    async def update_user_settings(self, user_id: str, **fields: object) -> None:
        if not fields:
            return
        fields["updated_at"] = datetime.now(UTC)
        async with self._engine.begin() as conn:
            await conn.execute(
                user_settings_table.update()
                .where(user_settings_table.c.user_id == user_id)
                .values(**fields)
            )

    # -- Trade CRUD ------------------------------------------------------------

    async def save_trade(self, trade: TradeRecord) -> str:
        async with self._engine.begin() as conn:
            await conn.execute(
                trades_table.insert().values(
                    id=trade.id,
                    user_id=trade.user_id,
                    symbol=trade.symbol,
                    side=trade.side,
                    quantity=trade.quantity,
                    price=trade.price,
                    commission=trade.commission,
                    strategy=trade.strategy,
                    paper=trade.paper,
                    timestamp=trade.timestamp,
                )
            )
        return trade.id

    async def get_trade(self, trade_id: str) -> TradeRecord | None:
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(trades_table.select().where(trades_table.c.id == trade_id))
            ).first()
        if row is None:
            return None
        return TradeRecord(**row._asdict())

    async def list_trades(
        self,
        strategy: str | None = None,
        limit: int = 100,
        user_id: str | None = None,
    ) -> list[TradeRecord]:
        query = trades_table.select().order_by(trades_table.c.timestamp.desc()).limit(limit)
        if user_id is not None:
            query = query.where(trades_table.c.user_id == user_id)
        if strategy:
            query = query.where(trades_table.c.strategy == strategy)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
        return [TradeRecord(**r._asdict()) for r in rows]

    async def save_signal(self, signal: SignalRecord) -> str:
        async with self._engine.begin() as conn:
            await conn.execute(
                signals_table.insert().values(
                    id=signal.id,
                    user_id=signal.user_id,
                    symbol=signal.symbol,
                    direction=signal.direction,
                    confidence=signal.confidence,
                    strategy=signal.strategy,
                    reasoning=signal.reasoning,
                    timestamp=signal.timestamp,
                )
            )
        return signal.id

    async def list_signals(
        self,
        limit: int = 100,
        user_id: str | None = None,
    ) -> list[SignalRecord]:
        query = signals_table.select().order_by(signals_table.c.timestamp.desc()).limit(limit)
        if user_id is not None:
            query = query.where(signals_table.c.user_id == user_id)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
        return [SignalRecord(**r._asdict()) for r in rows]

    async def load_ohlc_bars(self, records: list[OHLCRecord]) -> int:
        """Bulk upsert OHLC records in batches of 1000."""
        if not records:
            return 0
        batch_size = 1000
        total = 0
        is_pg = self._engine.dialect.name == "postgresql"
        async with self._engine.begin() as conn:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                for rec in batch:
                    values = {
                        "symbol": rec.symbol,
                        "interval": rec.interval,
                        "timestamp": rec.timestamp,
                        "open": rec.open,
                        "high": rec.high,
                        "low": rec.low,
                        "close": rec.close,
                        "volume": rec.volume,
                        "source": rec.source,
                    }
                    if is_pg:
                        stmt = pg_insert(ohlc_bars_table).values(**values)
                        stmt = stmt.on_conflict_do_update(
                            constraint=ohlc_bars_table.primary_key,
                            set_={
                                k: v
                                for k, v in values.items()
                                if k not in ("symbol", "interval", "timestamp")
                            },
                        )
                    else:
                        stmt = sqlite_insert(ohlc_bars_table).values(**values)
                        stmt = stmt.on_conflict_do_update(
                            set_={
                                k: v
                                for k, v in values.items()
                                if k not in ("symbol", "interval", "timestamp")
                            },
                        )
                    await conn.execute(stmt)
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

    # -- Feed CRUD -------------------------------------------------------------

    async def save_feed(self, feed: FeedRecord) -> str:
        async with self._engine.begin() as conn:
            await conn.execute(
                feeds_table.insert().values(
                    id=feed.id,
                    name=feed.name,
                    url=feed.url,
                    feed_type=feed.feed_type,
                    category=feed.category,
                    auth_type=feed.auth_type,
                    rate_limit_rpm=feed.rate_limit_rpm,
                    enabled=feed.enabled,
                    last_fetched_at=feed.last_fetched_at,
                    created_at=feed.created_at,
                )
            )
        return feed.id

    async def list_feeds(
        self,
        enabled_only: bool = False,
        feed_type: str | None = None,
    ) -> list[FeedRecord]:
        query = feeds_table.select().order_by(feeds_table.c.name.asc())
        if enabled_only:
            query = query.where(feeds_table.c.enabled.is_(True))
        if feed_type is not None:
            query = query.where(feeds_table.c.feed_type == feed_type)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
        return [
            FeedRecord(
                id=r.id,
                name=r.name,
                url=r.url,
                feed_type=r.feed_type,
                category=r.category,
                auth_type=r.auth_type,
                rate_limit_rpm=r.rate_limit_rpm,
                enabled=r.enabled,
                last_fetched_at=r.last_fetched_at,
                created_at=r.created_at,
            )
            for r in rows
        ]

    async def count_feeds(self) -> int:
        async with self._engine.connect() as conn:
            result = await conn.execute(sa.select(sa.func.count()).select_from(feeds_table))
            return int(result.scalar() or 0)

    async def seed_feeds(self, records: list[FeedRecord]) -> int:
        """Bulk insert feeds, ignoring duplicates (by URL)."""
        inserted = 0
        is_pg = self._engine.dialect.name == "postgresql"
        async with self._engine.begin() as conn:
            for rec in records:
                values = {
                    "id": rec.id,
                    "name": rec.name,
                    "url": rec.url,
                    "feed_type": rec.feed_type,
                    "category": rec.category,
                    "auth_type": rec.auth_type,
                    "rate_limit_rpm": rec.rate_limit_rpm,
                    "enabled": rec.enabled,
                    "last_fetched_at": rec.last_fetched_at,
                    "created_at": rec.created_at,
                }
                if is_pg:
                    stmt = pg_insert(feeds_table).values(**values)
                    stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
                else:
                    stmt = sqlite_insert(feeds_table).values(**values)
                    stmt = stmt.on_conflict_do_nothing(index_elements=["url"])
                await conn.execute(stmt)
                inserted += 1
        return inserted

    async def update_feed_last_fetched(self, feed_id: str, ts: datetime) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                feeds_table.update().where(feeds_table.c.id == feed_id).values(last_fetched_at=ts)
            )

    # -- Article CRUD ----------------------------------------------------------

    async def save_article(self, article: ArticleRecord) -> str | None:
        """Save an article. Returns article ID on success, None if duplicate."""
        try:
            async with self._engine.begin() as conn:
                await conn.execute(
                    articles_table.insert().values(
                        id=article.id,
                        content_hash=article.content_hash,
                        title=article.title,
                        body=article.body,
                        source=article.source,
                        url=article.url,
                        published_at=article.published_at,
                        fetched_at=article.fetched_at,
                        feed_id=article.feed_id,
                        created_at=article.created_at,
                    )
                )
                for symbol in article.symbols:
                    await conn.execute(
                        article_symbols_table.insert().values(
                            article_id=article.id,
                            symbol=symbol,
                        )
                    )
        except sa.exc.IntegrityError:
            return None
        return article.id

    async def get_articles_for_symbol(
        self,
        symbol: str,
        limit: int = 100,
    ) -> list[ArticleRecord]:
        query = (
            sa.select(articles_table)
            .join(article_symbols_table, articles_table.c.id == article_symbols_table.c.article_id)
            .where(article_symbols_table.c.symbol == symbol)
            .order_by(articles_table.c.published_at.desc())
            .limit(limit)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
            results = []
            for r in rows:
                syms = await self._get_article_symbols(conn, r.id)
                results.append(
                    ArticleRecord(
                        id=r.id,
                        content_hash=r.content_hash,
                        title=r.title,
                        body=r.body,
                        source=r.source,
                        url=r.url,
                        published_at=r.published_at,
                        fetched_at=r.fetched_at,
                        feed_id=r.feed_id,
                        created_at=r.created_at,
                        symbols=syms,
                    )
                )
        return results

    async def get_articles_for_symbol_by_id(
        self,
        article_id: str,
    ) -> list[ArticleRecord]:
        """Get an article by ID with its symbols."""
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(articles_table.select().where(articles_table.c.id == article_id))
            ).first()
            if row is None:
                return []
            syms = await self._get_article_symbols(conn, row.id)
            return [
                ArticleRecord(
                    id=row.id,
                    content_hash=row.content_hash,
                    title=row.title,
                    body=row.body,
                    source=row.source,
                    url=row.url,
                    published_at=row.published_at,
                    fetched_at=row.fetched_at,
                    feed_id=row.feed_id,
                    created_at=row.created_at,
                    symbols=syms,
                )
            ]

    async def _get_article_symbols(self, conn, article_id: str) -> list[str]:
        rows = (
            await conn.execute(
                article_symbols_table.select().where(
                    article_symbols_table.c.article_id == article_id
                )
            )
        ).fetchall()
        return [r.symbol for r in rows]

    async def get_unscored_articles(
        self,
        symbol: str,
        analyzer: str,
        limit: int = 100,
    ) -> list[ArticleRecord]:
        """Get articles for a symbol that have no score from the given analyzer."""
        scored_subq = sa.select(sentiment_scores_table.c.article_id).where(
            sentiment_scores_table.c.analyzer == analyzer
        )
        query = (
            sa.select(articles_table)
            .join(article_symbols_table, articles_table.c.id == article_symbols_table.c.article_id)
            .where(article_symbols_table.c.symbol == symbol)
            .where(articles_table.c.id.not_in(scored_subq))
            .order_by(articles_table.c.published_at.desc())
            .limit(limit)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
            results = []
            for r in rows:
                syms = await self._get_article_symbols(conn, r.id)
                results.append(
                    ArticleRecord(
                        id=r.id,
                        content_hash=r.content_hash,
                        title=r.title,
                        body=r.body,
                        source=r.source,
                        url=r.url,
                        published_at=r.published_at,
                        fetched_at=r.fetched_at,
                        feed_id=r.feed_id,
                        created_at=r.created_at,
                        symbols=syms,
                    )
                )
        return results

    # -- Sentiment Score CRUD --------------------------------------------------

    async def save_score(self, score: SentimentScoreRecord) -> str | None:
        """Save a sentiment score. Ignores duplicates (article_id + analyzer)."""
        try:
            async with self._engine.begin() as conn:
                await conn.execute(
                    sentiment_scores_table.insert().values(
                        id=score.id,
                        article_id=score.article_id,
                        score=score.score,
                        magnitude=score.magnitude,
                        reasoning=score.reasoning,
                        analyzer=score.analyzer,
                        created_at=score.created_at,
                    )
                )
        except sa.exc.IntegrityError:
            return None
        return score.id

    async def has_score(self, article_id: str, analyzer: str) -> bool:
        query = (
            sa.select(sa.func.count())
            .select_from(sentiment_scores_table)
            .where(sentiment_scores_table.c.article_id == article_id)
            .where(sentiment_scores_table.c.analyzer == analyzer)
        )
        async with self._engine.connect() as conn:
            result = await conn.execute(query)
            return int(result.scalar() or 0) > 0

    async def get_scores_as_of(
        self,
        symbols: list[str],
        as_of_dt: datetime,
        analyzer: str | None = None,
    ) -> list[tuple[str, float, float, datetime]]:
        """Return (symbol, score, magnitude, published_at) for articles published ≤ as_of_dt.

        Used exclusively for lookahead-free backtesting.
        """
        placeholders = ", ".join(f":sym{i}" for i in range(len(symbols)))
        params: dict = {f"sym{i}": s for i, s in enumerate(symbols)}
        params["as_of_dt"] = as_of_dt

        sql = f"""
            SELECT DISTINCT asym.symbol, ss.score, ss.magnitude, a.published_at
            FROM sentiment_scores ss
            JOIN articles a ON ss.article_id = a.id
            JOIN article_symbols asym ON a.id = asym.article_id
            WHERE asym.symbol IN ({placeholders})
              AND a.published_at <= :as_of_dt
            ORDER BY a.published_at ASC
        """

        if analyzer is not None:
            sql = f"""
                SELECT DISTINCT asym.symbol, ss.score, ss.magnitude, a.published_at
                FROM sentiment_scores ss
                JOIN articles a ON ss.article_id = a.id
                JOIN article_symbols asym ON a.id = asym.article_id
                WHERE asym.symbol IN ({placeholders})
                  AND a.published_at <= :as_of_dt
                  AND ss.analyzer = :analyzer
                ORDER BY a.published_at ASC
            """
            params["analyzer"] = analyzer

        async with self._engine.connect() as conn:
            rows = (await conn.execute(sa.text(sql), params)).fetchall()

        def _as_dt(val: object) -> datetime:
            if isinstance(val, datetime):
                return val if val.tzinfo else val.replace(tzinfo=UTC)
            dt = datetime.fromisoformat(str(val))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

        return [(r[0], float(r[1]), float(r[2]), _as_dt(r[3])) for r in rows]

    async def load_recent_scores(
        self,
        hours: int = 48,
    ) -> list[SentimentScoreRecord]:
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        query = (
            sentiment_scores_table.select()
            .where(sentiment_scores_table.c.created_at >= cutoff)
            .order_by(sentiment_scores_table.c.created_at.desc())
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
        return [
            SentimentScoreRecord(
                id=r.id,
                article_id=r.article_id,
                score=r.score,
                magnitude=r.magnitude,
                reasoning=r.reasoning,
                analyzer=r.analyzer,
                created_at=r.created_at,
            )
            for r in rows
        ]
