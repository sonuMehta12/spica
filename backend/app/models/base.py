from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from ulid import ULID

from app.db import Base


def new_id() -> str:
    """
    ULID — opaque, stable, sortable by creation time.

    Deliberately not derived from the row's contents: a content hash would bind
    identity to the de-duplication rule, so the day that rule changes every id
    moves and every reference to it breaks. De-duplication lives in its own
    column (`dedupe_key`) instead.
    """
    return str(ULID())


class Envelope:
    """
    The spine every record shares (spec/substrate.md). Repeated per table rather
    than held in one `records` table with a JSONB body — a shared table would
    cost typed columns, real indexes, and turn every report into JSONB
    extraction.
    """

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["Base", "Envelope", "new_id"]
