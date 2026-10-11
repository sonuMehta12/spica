"""
The conversation. One thread, kept forever, replayed in part.

There is no "new chat" button and there will not be one: the agent is the app,
and an app does not start over. So a single row in `conversations` per user,
and every turn appended to `messages`.

**What the model sees is not what the user sees.** The user scrolls the whole
history; the model gets the last twenty turns plus a rolling summary of
everything before them. Two reasons, and the second is the important one:
context costs money, and an old tool result is *stale* — yesterday's spend
replayed into today's context is a wrong number the model will happily quote.
So tool traffic is never replayed. Only what was said.
"""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Envelope


class Conversation(Envelope, Base):
    """One per user. The summary is everything before `summary_through_seq`."""

    __tablename__ = "conversations"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    # Prose, written by the model when turns fall out of the window. Facts
    # about the *conversation*, not about the data — the ledger is queried
    # fresh every turn, so a summary never carries a number forward.
    summary: Mapped[str | None] = mapped_column(Text)
    summary_through_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    #: What the user has cleared from view. Everything at or below it is hidden
    #: from the client's default read and nothing is deleted — the thread is
    #: still one thread. Clearing also compacts, so the marker and
    #: `summary_through_seq` move together. spec/done/chat-history.md.
    cleared_through_seq: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0")

    __table_args__ = (
        Index("uq_conversations_user", "user_id", unique=True,
              postgresql_where=text("deleted_at IS NULL")),
    )


class Message(Envelope, Base):
    """
    One turn. `seq` is per-conversation and monotonic, so "the last twenty" is
    an ORDER BY rather than a timestamp comparison that ties on a fast pair.

    `cards` is what the UI draws — the typed reply objects. `text` is the plain
    fallback and what the summariser reads. `tool_trace` records which tools ran
    with what arguments: kept for debugging and never replayed, because the
    numbers in it go stale the moment a row changes.
    """

    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role: Mapped[str] = mapped_column(String(9), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    cards: Mapped[list | None] = mapped_column(JSONB)
    tool_trace: Mapped[list | None] = mapped_column(JSONB)
    # What the turn cost, so "is this model worth it" is answerable from data.
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("role IN ('user','agent')", name="ck_messages_role"),
        Index("uq_messages_conv_seq", "conversation_id", "seq", unique=True),
    )
