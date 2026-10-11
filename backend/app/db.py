from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import Settings, settings


class Base(DeclarativeBase):
    """
    Every table carries the envelope from spec/substrate.md — id, type,
    timestamps, source, confidence, tags, deletedAt. Those columns are repeated
    per table rather than living in one `records` table with a JSONB body: a
    shared table would cost typed columns, real indexes, and turn every report
    into JSONB extraction.
    """


def make_engine(s: Settings) -> AsyncEngine:
    """The pool everywhere but Vercel, where `db_null_pool` says why not."""
    if s.db_null_pool:
        return create_async_engine(s.database_url, poolclass=NullPool)
    return create_async_engine(s.database_url, pool_pre_ping=True)


engine = make_engine(settings())
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


# One definition for every route, rather than each declaring its own.
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@asynccontextmanager
async def one_transaction(lock: str | None = None) -> AsyncIterator[AsyncSession]:
    """A session whose commits are savepoints inside one transaction: what the
    block writes lands together when it ends, or not at all if it raises.

    For a unit of work made of routes that each commit for themselves — the
    first run's answer, several writes that must not land halfway
    (spec/done/onboarding-goals.md § A turn). `create_savepoint` is SQLAlchemy's
    mode for a session joined to a transaction it does not own: its
    `commit()` releases a savepoint, and only this block commits.

    `lock` runs the blocks that share it one at a time. Such a transaction
    stays open for seconds — model calls happen inside it — so two at once for
    one person (an answer resent after the client gave up on the first) could
    take the same rows in opposite orders and deadlock. A transaction-scoped
    advisory lock, taken first, queues the second behind the first instead.
    """
    async with engine.connect() as conn, conn.begin():
        if lock is not None:
            await conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": lock})
        async with AsyncSession(bind=conn, join_transaction_mode="create_savepoint",
                                expire_on_commit=False) as session:
            yield session
            await session.commit()
