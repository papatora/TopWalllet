"""Async database engine/session factory. SQLite for MVP, Postgres-ready."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import settings
from src.db.models import Base

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        url = settings.database_url
        if url.startswith("sqlite"):
            # ensure the sqlite file's directory exists
            db_path = url.split("///")[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # timeout 120: busy_timeout SQLite — bridge contention singkat;
        # writer berat diserialisasi db_write_lock (S-43), ini pengaman
        # untuk writer kecil yang tidak memakai kunci (reverify dll).
        _engine = create_async_engine(url, echo=False, pool_pre_ping=True,
                                     connect_args={"timeout": 120} if url.startswith("sqlite") else {})
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def init_db() -> None:
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
