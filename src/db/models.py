"""SQLAlchemy 2.0 models. SQLite for MVP; the same schema runs on PostgreSQL
(see docker-compose.yml) by swapping DATABASE_URL."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Token(Base):
    """A token on the target chain, discovered via DexScreener or on-chain."""
    __tablename__ = "tokens"

    address: Mapped[str] = mapped_column(String(64), primary_key=True)  # lowercase CA
    symbol: Mapped[str] = mapped_column(String(64), default="")
    name: Mapped[str] = mapped_column(String(256), default="")
    decimals: Mapped[int] = mapped_column(Integer, default=18)
    price_usd: Mapped[float | None] = mapped_column(Float, nullable=True)  # last snapshot
    liquidity_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Pool(Base):
    """A DEX pool (Uniswap v4 poolId or v3 pool contract) for a token."""
    __tablename__ = "pools"

    address: Mapped[str] = mapped_column(String(80), primary_key=True)  # poolId / pool contract (lowercase)
    token_address: Mapped[str] = mapped_column(ForeignKey("tokens.address"), index=True)
    dex: Mapped[str] = mapped_column(String(32), default="")  # uniswap / ramses / giga ...
    version: Mapped[int] = mapped_column(Integer, default=4)  # 3 or 4
    quote_token: Mapped[str] = mapped_column(String(64), default="")  # lowercase
    quote_symbol: Mapped[str] = mapped_column(String(32), default="")
    liquidity_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_usd: Mapped[float | None] = mapped_column(Float, nullable=True)  # base token price in this pool


class Wallet(Base):
    __tablename__ = "wallets"

    address: Mapped[str] = mapped_column(String(64), primary_key=True)  # lowercase
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending | in_progress | enriched | failed | skipped
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_active: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")


class WalletTokenInterest(Base):
    """How a wallet was discovered in relation to a token (discovery edge)."""
    __tablename__ = "wallet_token_interest"
    __table_args__ = (UniqueConstraint("wallet_address", "token_address", "source", name="uq_interest"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(ForeignKey("wallets.address"), index=True)
    token_address: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(24))  # holder | trader | monitor | track_ca
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SwapEvent(Base):
    """A classified buy/sell of a token by a wallet (from explorer transfers)."""
    __tablename__ = "swap_events"
    __table_args__ = (UniqueConstraint("wallet_address", "tx_hash", "token_address", "side", name="uq_swap"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(ForeignKey("wallets.address"), index=True)
    token_address: Mapped[str] = mapped_column(String(64), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    block_num: Mapped[int] = mapped_column(BigInteger, default=0)
    side: Mapped[str] = mapped_column(String(4))  # BUY | SELL
    token_amount: Mapped[float] = mapped_column(Float)
    price_usd: Mapped[float | None] = mapped_column(Float, nullable=True)  # price at block, if series known
    usd_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    tx_hash: Mapped[str] = mapped_column(String(80), default="")


class PricePoint(Base):
    """Per-pool historical price samples derived from on-chain Swap events."""
    __tablename__ = "price_points"
    __table_args__ = (UniqueConstraint("pool_address", "block_num", name="uq_price_point"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pool_address: Mapped[str] = mapped_column(String(80), index=True)
    block_num: Mapped[int] = mapped_column(BigInteger)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price_usd: Mapped[float] = mapped_column(Float)


class BlockTimestamp(Base):
    """Cache of block number → timestamp (shared across pools)."""
    __tablename__ = "block_timestamps"

    block_num: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Position(Base):
    """A computed round-trip (or open) position of a wallet in a token."""
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_address: Mapped[str] = mapped_column(ForeignKey("wallets.address"), index=True)
    token_address: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(8))  # open | closed
    entry_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exit_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_price_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_price_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    size_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    hold_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_pctile: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0=lowest price of window
    exit_pctile: Mapped[float | None] = mapped_column(Float, nullable=True)   # 1=highest price of window
    current_price_usd: Mapped[float | None] = mapped_column(Float, nullable=True)


class WalletScore(Base):
    __tablename__ = "wallet_scores"

    wallet_address: Mapped[str] = mapped_column(ForeignKey("wallets.address"), primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    metrics: Mapped[str] = mapped_column(Text, default="{}")     # JSON blob
    trading_style: Mapped[str] = mapped_column(String(64), default="")
    risk_flags: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    cluster_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PipelineCheckpoint(Base):
    __tablename__ = "pipeline_checkpoints"

    stage: Mapped[str] = mapped_column(String(32), primary_key=True)
    cursor: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
